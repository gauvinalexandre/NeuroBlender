# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>


# =========================================================================== #


"""The NeuroBlender main module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
"""


# =========================================================================== #


import bpy

from bpy.app.handlers import persistent
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.types import (Panel,
                       Operator,
                       OperatorFileListElement,
                       PropertyGroup,
                       UIList,
                       Menu)
from bpy.props import (BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       EnumProperty,
                       FloatVectorProperty,
                       FloatProperty,
                       IntProperty,
                       IntVectorProperty,
                       PointerProperty)
from bl_operators.presets import AddPresetBase

import os
import sys
from shutil import copy
import numpy as np
import mathutils
import re

from . import neuroblender_import as nb_imp
from . import neuroblender_materials as nb_mat
from . import neuroblender_renderpresets as nb_rp
from . import neuroblender_beautify as nb_beau
from . import neuroblender_utils as nb_utils
from . import external_sitepackages as ext_sp


# =========================================================================== #


bl_info = {
    "name": "NeuroBlender",
    "author": "Michiel Kleinnijenhuis",
    "version": (0, 0, 6),
    "blender": (2, 78, 4),
    "location": "Properties -> Scene -> NeuroBlender",
    "description": "Create artwork from neuroscientific data.",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"}


# =========================================================================== #


class NeuroBlenderBasePanel(Panel):
    """Host the NeuroBlender base geometry"""
    bl_idname = "OBJECT_PT_nb_geometry"
    bl_label = "NeuroBlender - Base"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):

        scn = context.scene
        nb = scn.nb

        if nb.is_enabled:
            self.draw_nb_panel(self.layout, nb)
        else:
            self.drawunit_switch_to_main(self.layout, nb)

    def draw_nb_panel(self, layout, nb):

        row = layout.row()
        row.prop(nb, "objecttype", expand=True)

        row = layout.row()
        row.separator()

        self.drawunit_UIList(layout, "L1", nb, nb.objecttype)

        row = layout.row()
        row.separator()

        try:
            idx = eval("nb.index_%s" % nb.objecttype)
            nb_ob = eval("nb.%s[%d]" % (nb.objecttype, idx))
        except IndexError:
            pass
        else:
            if nb.objecttype == "surfaces":
                self.drawunit_tri(layout, "unwrap", nb, nb_ob)
            elif nb.objecttype == "voxelvolumes":
                self.drawunit_tri(layout, "slices", nb, nb_ob)

            self.drawunit_tri(layout, "material", nb, nb_ob)

            self.drawunit_tri(layout, "transform", nb, nb_ob)

            if nb.advanced:
                self.drawunit_tri(layout, "info", nb, nb_ob)

    def drawunit_switch_to_main(self, layout, nb):

        row = layout.row()
        row.label(text="Please use the main scene for NeuroBlender.")
        row = layout.row()
        row.operator("nb.switch_to_main",
                     text="Switch to main",
                     icon="FORWARD")

    def drawunit_UIList(self, layout, uilistlevel, data, obtype, addopt=True):

        row = layout.row()
        row.template_list("ObjectList" + uilistlevel, "",
                          data, obtype,
                          data, "index_" + obtype,
                          rows=2)
        col = row.column(align=True)
        if addopt:
            if ((uilistlevel == "L2") and
                    data.path_from_id().startswith("nb.voxelvolumes")):
                obtype = "voxelvolumes"
            col.operator("nb.import_" + obtype,
                         icon='ZOOMIN',
                         text="").parentpath = data.path_from_id()
        col.operator("nb.oblist_ops",
                     icon='ZOOMOUT',
                     text="").action = 'REMOVE_' + uilistlevel

        if bpy.context.scene.nb.advanced:
            col.menu("nb.mass_is_rendered_" + uilistlevel,
                     icon='DOWNARROW_HLT',
                     text="")
            col.separator()
            col.operator("nb.oblist_ops",
                         icon='TRIA_UP',
                         text="").action = 'UP_' + uilistlevel
            col.operator("nb.oblist_ops",
                         icon='TRIA_DOWN',
                         text="").action = 'DOWN_' + uilistlevel

    def drawunit_tri(self, layout, triflag, nb, data):

        row = layout.row()
        prop = "show_%s" % triflag
        if eval("nb.%s" % prop):
            exec("self.drawunit_tri_%s(layout, nb, data)" % triflag)
            icon = 'TRIA_DOWN'
            row.prop(nb, prop, icon=icon, emboss=False)

            row = layout.row()
            row.separator()
        else:
            icon = 'TRIA_RIGHT'
            row.prop(nb, prop, icon=icon, emboss=False)

    def drawunit_tri_unwrap(self, layout, nb, nb_ob):

        self.drawunit_unwrap(layout, nb_ob)

    def drawunit_unwrap(self, layout, nb_ob):

        row = layout.row()
        row.prop(nb_ob, "sphere", text="")
        row = layout.row()
        row.operator("nb.unwrap_surface", text="Unwrap from sphere")

    def drawunit_tri_slices(self, layout, nb, nb_ob):

        self.drawunit_slices(layout, nb_ob)

    def drawunit_slices(self, layout, nb_ob, is_yoked=False):

        row = layout.row()
        col = row.column()
        col.prop(nb_ob, "slicethickness", expand=True, text="Thickness")
        col.enabled = not is_yoked
        col = row.column()
        col.prop(nb_ob, "sliceposition", expand=True, text="Position")
        col.enabled = not is_yoked
        col = row.column()
        col.prop(nb_ob, "sliceangle", expand=True, text="Angle")
        col.enabled = not is_yoked

    def drawunit_tri_material(self, layout, nb, nb_ob):

        if nb.objecttype == "voxelvolumes":

            self.drawunit_rendertype(layout, nb_ob)

            tex = bpy.data.textures[nb_ob.name]
            self.drawunit_texture(layout, tex, nb_ob)

        else:

            self.drawunit_material(layout, nb_ob)

    def drawunit_material(self, layout, nb_ob):

        scn = bpy.context.scene
        nb = scn.nb

        if nb.engine.startswith("BLENDER"):

            self.drawunit_basic_blender(layout, nb_ob)

        else:

            row = layout.row()
            row.prop(nb_ob, "colourtype", expand=True)

            row = layout.row()
            row.separator()

            self.drawunit_basic_cycles(layout, nb_ob)

    def drawunit_basic_blender(self, layout, nb_ob):

        mat = bpy.data.materials[nb_ob.name]

        row = layout.row(align=True)
        row.prop(mat, "diffuse_color", text="")
        row.prop(mat, "alpha", text="Transparency")
        if hasattr(nb_ob, "colour"):
            row.operator("nb.revert_label", icon='BACK', text="")

    def drawunit_basic_cycles(self, layout, nb_ob):

        mat = bpy.data.materials[nb_ob.name]
        colour = mat.node_tree.nodes["RGB"].outputs[0]
        trans = mat.node_tree.nodes["Transparency"].outputs[0]

        row = layout.row(align=True)
        row.prop(colour, "default_value", text="")
        row.prop(trans, "default_value", text="Transparency")
        if hasattr(nb_ob, "colour"):
            row.operator("nb.revert_label", icon='BACK', text="")

        self.drawunit_basic_cycles_mix(layout, mat)

    def drawunit_basic_cycles_mix(self, layout, mat):

        nt = mat.node_tree

        row = layout.row(align=True)
        row.prop(nt.nodes["Diffuse BSDF"].inputs[1],
                 "default_value", text="diffuse")
        row.prop(nt.nodes["Glossy BSDF"].inputs[1],
                 "default_value", text="glossy")
        row.prop(nt.nodes["MixDiffGlos"].inputs[0],
                 "default_value", text="mix")

    def drawunit_texture(self, layout, tex, nb_coll=None, text=""):

        if text:
            row = layout.row()
            row.label(text=text)

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(tex, "intensity")
        row.prop(tex, "contrast")
#         row.prop(tex, "saturation")

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(tex, "use_color_ramp", text="Ramp")

        if tex.use_color_ramp:

            row = layout.row()
            row.separator()

            row = layout.row()
            row.prop(nb_coll, "colourmap_enum", expand=False)

            row = layout.row()
            row.separator()

            # NOTE: more fun stuff under Texture => Influence
            self.drawunit_colourramp(layout, tex, nb_coll)

        else:

            mat = bpy.data.materials[nb_coll.name]
            ts = mat.texture_slots.get(nb_coll.name)
            row.prop(ts, "color")

    def drawunit_colourramp(self, layout, ramp, nb_coll=None, text=""):

        if text:
            row = layout.row()
            row.label(text=text)

        row = layout.row()
        layout.template_color_ramp(ramp, "color_ramp", expand=True)

        if ((nb_coll is not None) and bpy.context.scene.nb.advanced):

            row = layout.row()
            row.separator()

            row = layout.row()
            row.label(text="non-normalized colour stop positions:")

            self.calc_nn_elpos(nb_coll, ramp)
            row = layout.row()
            row.enabled = False
            row.template_list("ObjectListCR", "",
                              nb_coll, "nn_elements",
                              nb_coll, "index_nn_elements",
                              rows=2)

            if hasattr(nb_coll, "showcolourbar"):

                row = layout.row()
                row.separator()

                row = layout.row()
                row.prop(nb_coll, "showcolourbar")

                if nb_coll.showcolourbar:

                    row = layout.row()
                    row.prop(nb_coll, "colourbar_size", text="size")
                    row.prop(nb_coll, "colourbar_position", text="position")

                    row = layout.row()
                    row.prop(nb_coll, "textlabel_colour", text="Textlabels")
                    row.prop(nb_coll, "textlabel_placement", text="")
                    row.prop(nb_coll, "textlabel_size", text="size")

    def calc_nn_elpos(self, nb_ov, ramp):

        # TODO: solve with drivers
        els = ramp.color_ramp.elements
        nnels = nb_ov.nn_elements
        n_els = len(els)
        n_nnels = len(nnels)
        if n_els > n_nnels:
            for _ in range(n_els-n_nnels):
                nnels.add()
        elif n_els < n_nnels:
            for _ in range(n_nnels-n_els):
                nnels.remove(0)
        dmin = nb_ov.range[0]
        dmax = nb_ov.range[1]
        drange = dmax-dmin
        for i, el in enumerate(nnels):
            el.name = "colour stop " + str(i)
            el.nn_position = els[i].position * drange + dmin

    def drawunit_rendertype(self, layout, nb_ob):

        row = layout.row()
        row.prop(nb_ob, "rendertype", expand=True)

        row = layout.row()
        row.separator()

        if nb_ob.rendertype == "SURFACE":
            mat = bpy.data.materials[nb_ob.name]
            row = layout.row()
            row.prop(mat, "alpha", text="SliceBox alpha")
            # NOTE: more fun stuff under Material => Transparency

    def drawunit_tri_transform(self, layout, nb, nb_ob):

        row = layout.row()
        row.prop(nb_ob, "sformfile", text="")

        if bpy.context.scene.nb.advanced:
            ob = bpy.data.objects[nb_ob.name]
            row = layout.row()
            col = row.column()
            col.prop(ob, "matrix_world")

    def drawunit_tri_info(self, layout, nb, nb_ob):

        row = layout.row()
        row.prop(nb_ob, "filepath")
        row.enabled = False

        funstring = 'self.drawunit_info_{}(layout, nb, nb_ob)'
        fun = funstring.format(nb.objecttype)
        eval(fun)

    def drawunit_info_tracts(self, layout, nb, nb_ob):

        row = layout.row()
        row.prop(nb_ob, "nstreamlines",
                 text="Number of streamlines", emboss=False)
        row.enabled = False

        row = layout.row()
        row.prop(nb_ob, "streamlines_interpolated",
                 text="Interpolation factor", emboss=False)
        row.enabled = False

        row = layout.row()
        row.prop(nb_ob, "tract_weeded",
                 text="Tract weeding factor", emboss=False)
        row.enabled = False

    def drawunit_info_surfaces(self, layout, nb, nb_ob):

        pass

    def drawunit_info_voxelvolumes(self, layout, nb, nb_ob):

        row = layout.row()
        row.prop(nb_ob, "texdir")

        row = layout.row()
        row.prop(nb_ob, "texformat")
        row.enabled = False

        row = layout.row()
        row.prop(nb_ob, "range", text="Datarange", emboss=False)
        row.enabled = False


class NeuroBlenderOverlayPanel(Panel):
    """Host the NeuroBlender overlay functions"""
    bl_idname = "OBJECT_PT_nb_overlays"
    bl_label = "NeuroBlender - Overlays"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    # delegate some methods
    draw = NeuroBlenderBasePanel.draw
    drawunit_switch_to_main = NeuroBlenderBasePanel.drawunit_switch_to_main
    drawunit_UIList = NeuroBlenderBasePanel.drawunit_UIList
    drawunit_tri = NeuroBlenderBasePanel.drawunit_tri
    drawunit_basic_blender = NeuroBlenderBasePanel.drawunit_basic_blender
    drawunit_basic_cycles = NeuroBlenderBasePanel.drawunit_basic_cycles
    drawunit_basic_cycles_mix = NeuroBlenderBasePanel.drawunit_basic_cycles_mix
    drawunit_rendertype = NeuroBlenderBasePanel.drawunit_rendertype
    drawunit_texture = NeuroBlenderBasePanel.drawunit_texture
    drawunit_colourramp = NeuroBlenderBasePanel.drawunit_colourramp
    calc_nn_elpos = NeuroBlenderBasePanel.calc_nn_elpos
    drawunit_slices = NeuroBlenderBasePanel.drawunit_slices

    def draw_nb_panel(self, layout, nb):

        try:
            ob_idx = eval("nb.index_%s" % nb.objecttype)
            nb_ob = eval("nb.%s[%d]" % (nb.objecttype, ob_idx))
        except IndexError:
            row = self.layout.row()
            row.label(text="No " + nb.objecttype + " loaded ...")
        else:
            self.draw_nb_overlaypanel(layout, nb, nb_ob)

    def draw_nb_overlaypanel(self, layout, nb, nb_ob):

        row = layout.row()
        row.prop(nb, "overlaytype", expand=True)

        row = layout.row()
        row.separator()

        self.drawunit_UIList(layout, "L2", nb_ob, nb.overlaytype)

        row = layout.row()
        row.separator()

        try:
            ov_idx = eval("nb_ob.index_%s" % nb.overlaytype)
            nb_ov = eval("nb_ob.%s[%d]" % (nb.overlaytype, ov_idx))
        except IndexError:
            pass
        else:
            self.draw_nb_overlayprops(layout, nb, nb_ob, nb_ov)

    def draw_nb_overlayprops(self, layout, nb, nb_ob, nb_ov):

        if nb.objecttype == "voxelvolumes":
            self.drawunit_tri(layout, "overlay_slices", nb, nb_ov)
        else:
            if nb.overlaytype == "scalargroups":
                if len(nb_ov.scalars) > 1:
                    row = layout.row()
                    row.template_list("ObjectListTS", "",
                                      nb_ov, "scalars",
                                      nb_ov, "index_scalars",
                                      rows=2, type="COMPACT")
                if nb.objecttype == 'surfaces':
                    self.drawunit_bake(layout)

        if nb.overlaytype == "scalargroups":
            self.drawunit_tri(layout, "overlay_material", nb, nb_ov)
        else:
            self.drawunit_tri(layout, "items", nb, nb_ov)

        if nb.advanced:
            self.drawunit_tri(layout, "overlay_info", nb, nb_ov)

    def drawunit_bake(self, layout):

        row = layout.row()
        row.separator()

        scn = bpy.context.scene
        nb = scn.nb

        row = layout.row()
        col = row.column()
        col.operator("nb.wp_preview", text="", icon="GROUP_VERTEX")
        col = row.column()
        col.operator("nb.vw2vc", text="", icon="GROUP_VCOL")
        col = row.column()
        col.operator("nb.vw2uv", text="", icon="GROUP_UVS")
        col = row.column()
        col.prop(nb, "uv_bakeall", toggle=True)

        row = layout.row()
        row.separator()

    def drawunit_tri_overlay_material(self, layout, nb, nb_ov):

        if nb.objecttype == "tracts":

            ng = bpy.data.node_groups.get("TractOvGroup")
            ramp = ng.nodes["ColorRamp"]
            self.drawunit_colourramp(layout, ramp, nb_ov)

        elif nb.objecttype == "surfaces":

            mat = bpy.data.materials[nb_ov.name]
            ramp = mat.node_tree.nodes["ColorRamp"]

            self.drawunit_colourramp(layout, ramp, nb_ov)

            row = layout.row()
            row.separator()

            self.drawunit_basic_cycles_mix(layout, mat)

        elif nb.objecttype == "voxelvolumes":

            self.drawunit_rendertype(layout, nb_ov)

            itemtype = nb.overlaytype.replace("groups", "s")
            item = eval("nb_ov.{0}[nb_ov.index_{0}]".format(itemtype))
            mat = bpy.data.materials[item.matname]
            tex = mat.texture_slots[item.tex_idx].texture
            self.drawunit_texture(layout, tex, nb_ov)

    def drawunit_tri_items(self, layout, nb, nb_ov):

        if nb.objecttype == "voxelvolumes":

            mat = bpy.data.materials[nb_ov.name]
            ts = mat.texture_slots.get(nb_ov.name)
            row = layout.row()
            row.prop(ts, "emission_factor")
            row.prop(ts, "emission_color_factor")

        itemtype = nb.overlaytype.replace("groups", "s")
        self.drawunit_UIList(layout, "L3", nb_ov, itemtype, addopt=False)

        self.drawunit_tri(layout, "itemprops", nb, nb_ov)
#         if itemtype == "labels":
#             if len(nb_ov.labels) < 33:  # TODO: proper method
#                 self.drawunit_tri(layout, "itemprops", nb, nb_ov)
#             else:
#                 self.drawunit_tri(layout, "overlay_material", nb, nb_ov)
#         else:
#             self.drawunit_tri(layout, "itemprops", nb, nb_ov)

    def drawunit_tri_itemprops(self, layout, nb, nb_ov):

        type = nb.overlaytype.replace("groups", "s")

        try:
            idx = eval("nb_ov.index_%s" % type)
            data = eval("nb_ov.%s[%d]" % (type, idx))
        except IndexError:
            pass
        else:
            exec("self.drawunit_%s(layout, nb, data)" % type)

    def drawunit_labels(self, layout, nb, nb_ov):

        if nb.objecttype == "voxelvolumes":

            nb_overlay = nb_utils.active_nb_overlay()[0]

            tex = bpy.data.textures[nb_overlay.name]
            el = tex.color_ramp.elements[nb_overlay.index_labels + 1]
            row = layout.row()
            row.prop(el, "color", text="")

        else:

            if nb.engine.startswith("BLENDER"):
                self.drawunit_basic_blender(layout, nb_ov)
            else:
                self.drawunit_basic_cycles(layout, nb_ov)

    def drawunit_borders(self, layout, nb, nb_ov):

        self.drawunit_basic_cycles(layout, nb_ov)

        row = layout.row()
        row.separator()

        ob = bpy.data.objects[nb_ov.name]

        row = layout.row()
        row.label(text="Smoothing:")
        row.prop(ob.modifiers["smooth"], "factor")
        row.prop(ob.modifiers["smooth"], "iterations")

        row = layout.row()
        row.label(text="Bevel:")
        row.prop(ob.data, "bevel_depth")
        row.prop(ob.data, "bevel_resolution")

    def drawunit_tri_overlay_slices(self, layout, nb, nb_ov):

        row = layout.row()
        row.prop(nb_ov, "is_yoked", text="Follow parent")
        self.drawunit_slices(layout, nb_ov, nb_ov.is_yoked)

    def drawunit_tri_overlay_info(self, layout, nb, nb_ov):

        row = layout.row()
        row.prop(nb_ov, "filepath")
        row.enabled = False

        if nb.overlaytype == "scalargroups":

            row = layout.row()
            row.prop(nb_ov, "texdir")

            row = layout.row()
            row.prop(nb_ov, "range")
#             row.enabled = False


class ObjectListL1(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        if item.is_valid:
            item_icon = item.icon
        else:
            item_icon = "CANCEL"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            col = layout.column()
            col.prop(item, "name", text="", emboss=False,
                     translate=False, icon=item_icon)

            if bpy.context.scene.nb.advanced:
                col = layout.column()
                col.alignment = "RIGHT"
                col.active = item.is_rendered
                col.prop(item, "is_rendered", text="", emboss=False,
                         translate=False, icon='SCENE')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListL2(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        if item.is_valid:
            item_icon = item.icon
        else:
            item_icon = "CANCEL"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            col = layout.column()
            col.prop(item, "name", text="", emboss=False,
                     translate=False, icon=item_icon)

            if bpy.context.scene.nb.advanced:
                col = layout.column()
                col.alignment = "RIGHT"
                col.active = item.is_rendered
                col.prop(item, "is_rendered", text="", emboss=False,
                         translate=False, icon='SCENE')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListL3(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        if item.is_valid:
            item_icon = item.icon
        else:
            item_icon = "CANCEL"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            col = layout.column()
            col.prop(item, "name", text="", emboss=False,
                     translate=False, icon=item_icon)

            if bpy.context.scene.nb.advanced:
                col = layout.column()
                col.alignment = "RIGHT"
                col.enabled = False
                col.prop(item, "value", text="", emboss=False)

                col = layout.column()
                col.alignment = "RIGHT"
                col.enabled = False
                col.prop(item, "colour", text="")

                col = layout.column()
                col.alignment = "RIGHT"
                col.active = item.is_rendered
                col.prop(item, "is_rendered", text="", emboss=False,
                         translate=False, icon='SCENE')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListCR(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        item_icon = "FULLSCREEN_ENTER"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            col = layout.column()
            col.prop(item, "name", text="", emboss=False,
                     translate=False, icon=item_icon)
            col = layout.column()
            col.prop(item, "nn_position", text="")
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListPL(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        if item.is_valid:
            item_icon = item.icon
        else:
            item_icon = "CANCEL"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            col = layout.column()
            col.prop(item, "name", text="", emboss=False,
                     translate=False, icon=item_icon)

            if bpy.context.scene.nb.advanced:
                col = layout.column()
                col.alignment = "RIGHT"
                col.active = item.is_rendered
                col.prop(item, "is_rendered", text="", emboss=False,
                         translate=False, icon='SCENE')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListAN(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        if item.is_valid:
            item_icon = item.icon
        else:
            item_icon = "CANCEL"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            col = layout.column()
            col.prop(item, "name", text="", emboss=False,
                     translate=False, icon=item_icon)

            if bpy.context.scene.nb.advanced:
                col = layout.column()
                col.alignment = "RIGHT"
                col.active = item.is_rendered
                col.prop(item, "is_rendered", text="", emboss=False,
                         translate=False, icon='SCENE')

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListCP(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        item_icon = "CANCEL"
        if self.layout_type in {'DEFAULT', 'COMPACT'}:

            row = layout.row()
            row.prop(item, "co", text="cp", emboss=True, icon=item_icon)

        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListTS(UIList):

    def draw_item(self, context, layout, data, item, icon,
                  active_data, active_propname, index):

        if item.is_valid:
            item_icon = item.icon
        else:
            item_icon = "CANCEL"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text="Time index:")
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.prop(text="", icon=item_icon)


class ObjectListOperations(Operator):
    bl_idname = "nb.oblist_ops"
    bl_label = "Objectlist operations"
    bl_options = {"REGISTER", "UNDO"}

    action = bpy.props.EnumProperty(
        items=(('UP_L1', "UpL1", ""),
               ('DOWN_L1', "DownL1", ""),
               ('REMOVE_L1', "RemoveL1", ""),
               ('UP_L2', "UpL2", ""),
               ('DOWN_L2', "DownL2", ""),
               ('REMOVE_L2', "RemoveL2", ""),
               ('UP_L3', "UpL3", ""),
               ('DOWN_L3', "DownL3", ""),
               ('REMOVE_L3', "RemoveL3", ""),
               ('UP_PL', "UpPL", ""),
               ('DOWN_PL', "DownPL", ""),
               ('REMOVE_PL', "RemovePL", ""),
               ('UP_CP', "UpCP", ""),
               ('DOWN_CP', "DownCP", ""),
               ('REMOVE_CP', "RemoveCP", ""),
               ('UP_AN', "UpAN", ""),
               ('DOWN_AN', "DownAN", ""),
               ('REMOVE_AN', "RemoveAN", "")))

    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")
    type = StringProperty(
        name="type",
        description="Specify object type",
        default="")
    index = IntProperty(
        name="index",
        description="Specify object index",
        default=-1)
    name = StringProperty(
        name="name",
        description="Specify object name",
        default="")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        collection, data, nb_ob = self.get_collection(context)

        try:
            item = collection[self.index]
        except IndexError:
            pass
        else:
            if self.action.startswith('REMOVE'):
                info = ['removed %s' % (collection[self.index].name)]
                info += self.remove_items(nb, data, collection, nb_ob)
                self.report({'INFO'}, '; '.join(info))
            elif (self.action.startswith('DOWN') and
                self.index < len(collection) - 1):
                collection.move(self.index, self.index + 1)
                exec("%s.index_%s += 1" % (data, self.type))
            elif self.action.startswith('UP') and self.index >= 1:
                collection.move(self.index, self.index - 1)
                exec("%s.index_%s -= 1" % (data, self.type))

        if self.type == "voxelvolumes":
            self.update_voxelvolume_drivers(nb)

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        if self.action.endswith('_L1'):
            nb_ob = nb_utils.active_nb_object()[0]
            self.type = nb.objecttype
            self.name = nb_ob.name
            self.index = eval("nb.%s.find(self.name)" % self.type)
            self.data_path = nb_ob.path_from_id()
        elif self.action.endswith('_L2'):
            nb_ob = nb_utils.active_nb_object()[0]
            nb_ov = nb_utils.active_nb_overlay()[0]
            self.type = nb.overlaytype
            self.name = nb_ov.name
            self.index = eval("nb_ob.%s.find(self.name)" % self.type)
            self.data_path = nb_ov.path_from_id()
        elif self.action.endswith('_L3'):
            nb_ob = nb_utils.active_nb_object()[0]
            nb_ov = nb_utils.active_nb_overlay()[0]
            nb_it = nb_utils.active_nb_overlayitem()[0]
            self.type = nb.overlaytype.replace("groups", "s")
            self.name = nb_it.name
            self.index = eval("nb_ov.%s.find(self.name)" % self.type)
            self.data_path = nb_it.path_from_id()
        elif self.action.endswith('_PL'):
            preset = eval("nb.presets[%d]" % nb.index_presets)
            light = preset.lights[preset.index_lights]
            self.type = "lights"
            self.name = light.name
            self.index = preset.index_lights
            self.data_path = light.path_from_id()
        elif self.action.endswith('_AN'):
            preset = eval("nb.presets[%d]" % nb.index_presets)
            animation = preset.animations[preset.index_animations]
            self.type = "animations"
            self.name = animation.name
            self.index = preset.index_animations
            self.data_path = animation.path_from_id()

        return self.execute(context)

    def get_collection(self, context):

        scn = context.scene
        nb = scn.nb

        try:
            self.data_path = eval("%s.path_from_id()" % self.data_path)
        except SyntaxError:
            self.report({'INFO'}, 'empty data path')
#             # try to construct data_path from type, index, name?
#             if type in ['tracts', 'surfaces', 'voxelvolumes']:
#                 self.data_path = ''
            return {"CANCELLED"}
        except NameError:
            self.report({'INFO'}, 'invalid data path: %s' % self.data_path)
            return {"CANCELLED"}

        dp_split = re.findall(r"[\w']+", self.data_path)
        dp_indices = re.findall(r"(\[\d+\])", self.data_path)
        collection = eval(self.data_path.strip(dp_indices[-1]))
        coll_path = collection.path_from_id()
        data = '.'.join(coll_path.split('.')[:-1])

        if self.index == -1:
            self.index = int(dp_split[-1])
        if not self.type:
            self.type = dp_split[-2]
        if not self.name:
            self.name = collection[self.index].name

        nb_ob = eval('.'.join(self.data_path.split('.')[:2]))

        return collection, data, nb_ob

    def remove_items(self, nb, data, collection, nb_ob):
        """Remove items from NeuroBlender."""

        info = []

        name = collection[self.index].name

        if self.action.endswith('_L1'):
            try:
                ob = bpy.data.objects[name]
            except KeyError:
                infostring = 'object "%s" not found'
                info += [infostring % name]
            else:
                if self.type == 'voxelvolumes':
                    self.remove_material(ob, name)
                    try:
                        slicebox = bpy.data.objects[name+"SliceBox"]
                    except KeyError:
                        infostring = 'slicebox "%s" not found'
                        info += [infostring % name+"SliceBox"]
                    else:
                        for ms in ob.material_slots:
                            self.remove_material(ob, ms.name)
                        bpy.data.objects.remove(slicebox)
                # remove all children
                fun = eval("self.remove_%s_overlays" % self.type)
                fun(nb_ob, ob)
                # remove the object itself
                bpy.data.objects.remove(ob)
        elif self.action.endswith('_PL'):
            try:
                ob = bpy.data.objects[name]
            except KeyError:
                infostring = 'object "%s" not found'
                info += [infostring % name]
            else:
                bpy.data.objects.remove(ob)
        elif self.action.endswith('_AN'):
            nb_preset = eval("nb.presets[%d]" % nb.index_presets)
            anim = nb_preset.animations[nb_preset.index_animations]
            fun = eval("self.remove_animations_%s" % 
                       anim.animationtype.lower())
            fun(nb_preset.animations, self.index)
        else:
            nb_ov, ov_idx = nb_utils.active_nb_overlay()
            ob = bpy.data.objects[nb_ob.name]
            fun = eval("self.remove_%s_%s" % (nb.objecttype, self.type))
            fun(collection[self.index], ob)

        collection.remove(self.index)
        exec("%s.index_%s -= 1" % (data, self.type))

        return info

    def remove_tracts_overlays(self, tract, ob):
        """Remove tract scalars and labels."""

        for sg in tract.scalargroups:
            self.remove_tracts_scalargroups(sg, ob)

    def remove_surfaces_overlays(self, surface, ob):
        """Remove surface scalars, labels and borders."""

        for sg in surface.scalargroups:
            self.remove_surfaces_scalargroups(sg, ob)
        for lg in surface.labelgroups:
            self.remove_surfaces_labelgroups(lg, ob)
        for bg in surface.bordergroups:
            self.remove_surfaces_bordergroups(bg, ob)

    def remove_voxelvolumes_overlays(self, nb_ob, ob):
        """Remove voxelvolume scalars and labels."""

        for sg in nb_ob.scalargroups:
            self.remove_voxelvolumes_scalargroups(sg, ob)
        for lg in nb_ob.labelgroups:
            self.remove_voxelvolumes_labelgroups(lg, ob)

    def remove_tracts_scalargroups(self, scalargroup, ob):
        """Remove scalar overlay from tract."""

        for scalar in scalargroup.scalars:
            for i, spline in enumerate(ob.data.splines):
                splname = scalar.name + '_spl' + str(i).zfill(8)
                self.remove_material(ob, splname)
                self.remove_image(ob, splname)

    def remove_surfaces_scalargroups(self, scalargroup, ob):  # TODO: check
        """Remove scalar overlay from a surface."""

        vgs = ob.vertex_groups
        vcs = ob.data.vertex_colors
        self.remove_vertexcoll(vgs, scalargroup.name)
        self.remove_vertexcoll(vcs, scalargroup.name)
        self.remove_material(ob, scalargroup.name)
        # TODO: remove colourbars

    def remove_surfaces_labelgroups(self, labelgroup, ob):
        """Remove label group."""

        for label in labelgroup.labels:
            self.remove_surfaces_labels(label, ob)

    def remove_surfaces_labels(self, label, ob):
        """Remove label from a labelgroup."""

        vgs = ob.vertex_groups
        self.remove_vertexcoll(vgs, label.name)
        self.remove_material(ob, label.name)

    def remove_surfaces_bordergroups(self, bordergroup, ob):
        """Remove a bordergroup overlay from a surface."""

        for border in bordergroup.borders:
            self.remove_surfaces_borders(border, ob)
        bg_ob = bpy.data.objects.get(bordergroup.name)
        bpy.data.objects.remove(bg_ob)

    def remove_surfaces_borders(self, border, ob):
        """Remove border from a bordergroup."""

        self.remove_material(ob, border.name)
        b_ob = bpy.data.objects[border.name]
        bpy.data.objects.remove(b_ob)

    def remove_voxelvolumes_scalargroups(self, scalargroup, ob):
        """Remove scalar overlay from a voxelvolume."""

        self.remove_material(ob, scalargroup.name)
        sg_ob = bpy.data.objects[scalargroup.name]
        bpy.data.objects.remove(sg_ob)
        sg_ob = bpy.data.objects[scalargroup.name + 'SliceBox']
        bpy.data.objects.remove(sg_ob)

    def remove_voxelvolumes_labelgroups(self, labelgroup, ob):
        """Remove labelgroup overlay from a voxelvolume."""

        self.remove_material(ob, labelgroup.name)
        lg_ob = bpy.data.objects[labelgroup.name]
        bpy.data.objects.remove(lg_ob)
        lg_ob = bpy.data.objects[labelgroup.name + 'SliceBox']
        bpy.data.objects.remove(lg_ob)

    def remove_voxelvolumes_labels(self, label, ob):
        """Remove label from a labelgroup."""

        self.remove_material(ob, label.name)
        l_ob = bpy.data.objects[label.name]
        bpy.data.objects.remove(l_ob)

    def remove_material(self, ob, name):
        """Remove a material."""

        ob_mats = ob.data.materials
        mat_idx = ob_mats.find(name)
        if mat_idx != -1:
            ob_mats.pop(mat_idx, update_data=True)

        self.remove_data(bpy.data.materials, name)

    def remove_image(self, ob, name):
        """Remove an image."""

        self.remove_data(bpy.data.images, name)

    def remove_data(self, coll, name):
        """Remove data if it is only has a single user."""

        item = coll.get(name)
        if (item is not None) and (item.users < 2):
            item.user_clear()
            coll.remove(item)

    def remove_vertexcoll(self, coll, name):
        """Remove vertexgroup or vertex_color attribute"""

        mstring = '{}.vol....'.format(name)
        for item in coll:
            if re.match(mstring, item.name) is not None:
                coll.remove(item)

    def update_voxelvolume_drivers(self, nb):
        """Update the data path in the drivers of voxelvolumes slicers."""

        for i, vvol in enumerate(nb.voxelvolumes):
            slicebox = bpy.data.objects[vvol.name+"SliceBox"]
            for dr in slicebox.animation_data.drivers:
                for var in dr.driver.variables:
                    for tar in var.targets:
                        dp = tar.data_path
                        idx = 16
                        if dp.index("nb.voxelvolumes[") == 0:
                            newpath = dp[:idx] + "%d" % i + dp[idx + 1:]
                            tar.data_path = dp[:idx] + "%d" % i + dp[idx + 1:]

    def remove_animations_camerapath(self, anims, index):
        """Remove camera path animation."""

        cam = bpy.data.objects['Cam']
        nb_rp.clear_camera_path_animation(cam, anims[index])
        cam_anims = [anim for i, anim in enumerate(anims)
                     if ((anim.animationtype == "CameraPath") &
                         (anim.is_rendered) &
                         (i != index))]
        nb_rp.update_cam_constraints(cam, cam_anims)

    def remove_animations_slices(self, anims, index):
        """Remove slice animation."""

        anim = anims[index]
        vvol = bpy.data.objects[anim.anim_voxelvolume]
        vvol.animation_data_clear()

    def remove_animations_timeseries(self, anims, index):
        """Remove timeseries animation."""

        pass  # TODO


class MassIsRenderedL1(Menu):
    bl_idname = "nb.mass_is_rendered_L1"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_L1'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_L1'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_L1'


class MassIsRenderedL2(Menu):
    bl_idname = "nb.mass_is_rendered_L2"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_L2'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_L2'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_L2'


class MassIsRenderedL3(Menu):
    bl_idname = "nb.mass_is_rendered_L3"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_L3'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_L3'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_L3'


class MassIsRenderedPL(Menu):
    bl_idname = "nb.mass_is_rendered_PL"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_PL'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_PL'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_PL'


class MassIsRenderedAN(Menu):
    bl_idname = "nb.mass_is_rendered_AN"
    bl_label = "Animation Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_AN'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_AN'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_AN'


class MassIsRenderedCP(Menu):
    bl_idname = "nb.mass_is_rendered_CP"
    bl_label = "Vertex Group Specials"
    bl_description = "Menu for group selection of rendering option"
    bl_options = {"REGISTER"}

    def draw(self, context):
        layout = self.layout
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Select All").action = 'SELECT_CP'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Deselect All").action = 'DESELECT_CP'
        layout.operator("nb.mass_select",
                        icon='SCENE',
                        text="Invert").action = 'INVERT_CP'


class MassSelect(Operator):
    bl_idname = "nb.mass_select"
    bl_label = "Mass select"
    bl_description = "Select/Deselect/Invert rendered objects/overlays"
    bl_options = {"REGISTER"}

    action = bpy.props.EnumProperty(
        items=(('SELECT_L1', "Select_L1", ""),
               ('DESELECT_L1', "Deselect_L1", ""),
               ('INVERT_L1', "Invert_L1", ""),
               ('SELECT_L2', "Select_L2", ""),
               ('DESELECT_L2', "Deselect_L2", ""),
               ('INVERT_L2', "Invert_L2", ""),
               ('SELECT_L3', "Select_L3", ""),
               ('DESELECT_L3', "Deselect_L3", ""),
               ('INVERT_L3', "Invert_L3", ""),
               ('SELECT_PL', "Select_PL", ""),
               ('DESELECT_PL', "Deselect_PL", ""),
               ('INVERT_PL', "Invert_PL", ""),
               ('SELECT_CP', "Select_CP", ""),
               ('DESELECT_CP', "Deselect_CP", ""),
               ('INVERT_CP', "Invert_CP", ""),
               ('SELECT_AN', "Select_AN", ""),
               ('DESELECT_AN', "Deselect_AN", ""),
               ('INVERT_AN', "Invert_AN", "")))

    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")
    type = StringProperty(
        name="type",
        description="Specify object type",
        default="")
    index = IntProperty(
        name="index",
        description="Specify object index",
        default=-1)
    name = StringProperty(
        name="name",
        description="Specify object name",
        default="")

    invoke = ObjectListOperations.invoke
    get_collection = ObjectListOperations.get_collection

    def execute(self, context):

        collection = self.get_collection(context)[0]

        for item in collection:
            if self.action.startswith('SELECT'):
                item.is_rendered = True
            elif self.action.startswith('DESELECT'):
                item.is_rendered = False
            elif self.action.startswith('INVERT'):
                item.is_rendered = not item.is_rendered

        return {"FINISHED"}


class ImportTracts(Operator, ImportHelper):
    bl_idname = "nb.import_tracts"
    bl_label = "Import tracts"
    bl_description = "Import tracts as curves"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)
    filter_glob = StringProperty(
        options={"HIDDEN"},
        default="*.vtk;" +
                "*.bfloat;*.Bfloat;*.bdouble;*.Bdouble;" +
                "*.tck;*.trk;" +
                "*.npy;*.npz;*.dpy")
        # NOTE: multiline comment not working here

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")
    interpolate_streamlines = FloatProperty(
        name="Interpolate streamlines",
        description="Interpolate the individual streamlines",
        default=1.,
        min=0.,
        max=1.)
    weed_tract = FloatProperty(
        name="Tract weeding",
        description="Retain a random selection of streamlines",
        default=1.,
        min=0.,
        max=1.)

    beautify = BoolProperty(
        name="Beautify",
        description="Apply initial bevel on streamlines",
        default=True)
    colourtype = EnumProperty(
        name="",
        description="Apply this tract colour method",
        default="primary6",
        items=[("none", "none", "none", 1),
               ("golden_angle", "golden_angle", "golden_angle", 2),
               ("primary6", "primary6", "primary6", 3),
               ("random", "random", "random", 4),
               ("directional", "directional", "directional", 5),
               ("pick", "pick", "pick", 6)])
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour for the tract(s)",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR")
    transparency = FloatProperty(
        name="Transparency",
        description="Set the transparency",
        default=1.,
        min=0.,
        max=1.)

    def execute(self, context):

        importtype = "tracts"
        impdict = {"weed_tract": self.weed_tract,
                   "interpolate_streamlines": self.interpolate_streamlines}
        beaudict = {"mode": "FULL",
                    "depth": 0.5,
                    "res": 10}

        self.import_objects(importtype, impdict, beaudict)

        return {"FINISHED"}

    def import_objects(self, importtype, impdict, beaudict):

        scn = bpy.context.scene
        nb = scn.nb

        importfun = eval("nb_imp.import_%s" % importtype[:-1])

        filenames = [file.name for file in self.files]
        if not filenames:
            filenames = os.listdir(self.directory)

        for f in filenames:
            fpath = os.path.join(self.directory, f)

            ca = [bpy.data.objects, bpy.data.meshes,
                  bpy.data.materials, bpy.data.textures]
            name = nb_utils.check_name(self.name, fpath, ca)

            obs, info_imp, info_geom = importfun(fpath, name, "", impdict)

            for ob in obs:
                try:
                    self.beautify
                except:  # force updates on voxelvolumes
                    nb.index_voxelvolumes = nb.index_voxelvolumes
#                     item.rendertype = item.rendertype  # FIXME
                else:
                    info_mat = nb_mat.materialise(ob,
                                                  self.colourtype,
                                                  self.colourpicker,
                                                  self.transparency)
                    info_beau = nb_beau.beautify_brain(ob,
                                                       importtype,
                                                       self.beautify,
                                                       beaudict)

            info = info_imp
            if nb.verbose:
                info = info + "\nname: '%s'\npath: '%s'\n" % (name, fpath)
                info = info + "%s\n%s\n%s" % (info_geom, info_mat, info_beau)

            self.report({'INFO'}, info)

    def draw(self, context):
        layout = self.layout

        row = self.layout.row()
        row.prop(self, "name")
        row = self.layout.row()
        row.prop(self, "interpolate_streamlines")
        row = self.layout.row()
        row.prop(self, "weed_tract")

        row = self.layout.row()
        row.separator()
        row = self.layout.row()
        row.prop(self, "beautify")
        row = self.layout.row()
        row.label(text="Colour: ")
        row = self.layout.row()
        row.prop(self, "colourtype")
        row = self.layout.row()
        if self.colourtype == "pick":
            row.prop(self, "colourpicker")
        row = self.layout.row()
        row.prop(self, "transparency")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class ImportSurfaces(Operator, ImportHelper):
    bl_idname = "nb.import_surfaces"
    bl_label = "Import surfaces"
    bl_description = "Import surfaces as mesh data"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)
    filter_glob = StringProperty(
        options={"HIDDEN"},
        default="*.obj;*.stl;" +
                "*.gii;" +
                "*.white;*.pial;*.inflated;*.sphere;*.orig;" +
                "*.blend")
        # NOTE: multiline comment not working here

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")
    beautify = BoolProperty(
        name="Beautify",
        description="Apply initial smoothing on surfaces",
        default=True)
    colourtype = EnumProperty(
        name="",
        description="Apply this surface colour method",
        default="primary6",
        items=[("none", "none", "none", 1),
               ("golden_angle", "golden_angle", "golden_angle", 2),
               ("primary6", "primary6", "primary6", 3),
               ("random", "random", "random", 4),
               ("directional", "directional", "directional", 5),
               ("pick", "pick", "pick", 6)])
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour for the tract(s)",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR")
    transparency = FloatProperty(
        name="Transparency",
        description="Set the transparency",
        default=1.,
        min=0.,
        max=1.)

    import_objects = ImportTracts.import_objects

    def execute(self, context):

        importtype = "surfaces"
        impdict = {}
        beaudict = {"iterations": 10,
                    "factor": 0.5,
                    "use_x": True,
                    "use_y": True,
                    "use_z": True}

        self.import_objects(importtype, impdict, beaudict)

        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout

        row = self.layout.row()
        row.prop(self, "name")

        row = self.layout.row()
        row.prop(self, "beautify")

        row = self.layout.row()
        row.label(text="Colour: ")
        row = self.layout.row()
        row.prop(self, "colourtype")
        row = self.layout.row()
        if self.colourtype == "pick":
            row.prop(self, "colourpicker")
        row = self.layout.row()
        row.prop(self, "transparency")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


def file_update(self, context):
    """Set the voxelvolume name according to the selected file."""

    ca = [bpy.data.meshes,
          bpy.data.materials,
          bpy.data.textures]
    self.name = nb_utils.check_name(self.files[0].name, "", ca)


def name_update(self, context):
    """Set the texture directory to the voxelvolume name."""

    self.texdir = "//voltex_%s" % self.name


def texdir_update(self, context):
    """Evaluate if a valid texture directory exists."""

    self.has_valid_texdir = nb_imp.check_texdir(self.texdir,
                                                self.texformat,
                                                overwrite=False)


def is_overlay_update(self, context):
    """Switch the parentpath base/overlay."""

    if self.is_overlay:
        try:
            nb_ob = nb_utils.active_nb_object()[0]
        except IndexError:
            pass  # no nb_obs found
        else:
            self.parentpath = nb_ob.path_from_id()
    else:
        self.parentpath = context.scene.nb.path_from_id()


def h5_dataset_callback(self, context):
    """Populate the enum based on available options."""

    names = []

    def h5_dataset_add(name, obj):
        if isinstance(obj.id, h5py.h5d.DatasetID):
            names.append(name)

    try:
        import h5py
        f = h5py.File(os.path.join(self.directory, self.files[0].name), 'r')
    except:
        items = [("no data", "no data", "not a valid h5", 0)]
    else:
        f.visititems(h5_dataset_add)
        f.close()
        items = [(name, name, "List the datatree", i)
                 for i, name in enumerate(names)]

        return items


class ImportVoxelvolumes(Operator, ImportHelper):
    bl_idname = "nb.import_voxelvolumes"
    bl_label = "Import voxelvolumes"
    bl_description = "Import voxelvolumes to textures"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath", type=OperatorFileListElement)
    filter_glob = StringProperty(
        options={"HIDDEN"},
        default="*.nii;*.nii.gz;*.img;*.hdr;" +
                "*.h5;" +
                "*.png;*.jpg;*.tif;*.tiff;")
        # NOTE: multiline comment not working here

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="voxelvolume",
        update=name_update)
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")
    name_mode = EnumProperty(
        name="nm",
        description="...",
        default="filename",
        items=[("filename", "filename", "filename", 0),
               ("custom", "custom", "custom", 1)])
    is_overlay = BoolProperty(
        name="Is overlay",
        description="...",
        default=False,
        update=is_overlay_update)
    is_label = BoolProperty(
        name="Is label",
        description="...",
        default=False)
    sformfile = StringProperty(
        name="sformfile",
        description="",
        default="",
        subtype="FILE_PATH")
    has_valid_texdir = BoolProperty(
        name="has_valid_texdir",
        description="...",
        default=False)
    texdir = StringProperty(
        name="Texture directory",
        description="The directory with textures",
        subtype="DIR_PATH",
        default="//",
        update=texdir_update)
    texformat = EnumProperty(
        name="Volume texture file format",
        description="Choose a format to save volume textures",
        default="IMAGE_SEQUENCE",
        items=[("IMAGE_SEQUENCE", "IMAGE_SEQUENCE", "IMAGE_SEQUENCE", 0),
               ("STRIP", "STRIP", "STRIP", 1),
               ("RAW_8BIT", "RAW_8BIT", "RAW_8BIT", 2)],
        update=texdir_update)
    overwrite = BoolProperty(
        name="overwrite",
        description="Overwrite existing texture directory",
        default=False)
    dataset = EnumProperty(
        name="Dataset",
        description="The the name of the hdf5 dataset",
        items=h5_dataset_callback)
    vol_idx = IntProperty(
        name="Volume index",
        description="The index of the volume to import (-1 for all)",
        default=-1)

    import_objects = ImportTracts.import_objects

    def execute(self, context):

        importtype = "voxelvolumes"
        impdict = {"is_overlay": self.is_overlay,
                   "is_label": self.is_label,
                   "parentpath": self.parentpath,
                   "texdir": self.texdir,
                   "texformat": self.texformat,
                   "overwrite": self.overwrite,
                   "dataset": self.dataset,
                   "vol_idx": self.vol_idx}
        beaudict = {}

        self.import_objects(importtype, impdict, beaudict)

        return {"FINISHED"}

    def draw(self, context):

        scn = context.scene
        nb = scn.nb

        layout = self.layout

        # FIXME: solve with update function
        if self.name_mode == "filename":
            voltexdir = [s for s in self.directory.split('/')
                         if "voltex_" in s]
              # FIXME: generalize to other namings
            if voltexdir:
                self.name = voltexdir[0][7:]
            else:
                try:
                    self.name = self.files[0].name
                except IndexError:
                    pass

        row = layout.row()
        row.prop(self, "name_mode", expand=True)

        row = layout.row()
        row.prop(self, "name")

        if self.files[0].name.endswith('.h5'):
            row = layout.row()
            row.prop(self, "dataset", expand=False)

        row = layout.row()
        row.prop(self, "vol_idx")

        row = layout.row()
        row.prop(self, "sformfile")

        row = layout.row()
        col = row.column()
        col.prop(self, "is_overlay")
        col = row.column()
        col.prop(self, "is_label")
        col.enabled = self.is_overlay
        row = layout.row()
        row.prop(self, "parentpath")
        row.enabled = self.is_overlay

        row = layout.row()
        row.prop(self, "texdir")
        row = layout.row()
        row.prop(self, "texformat")
        row = layout.row()
        row.prop(self, "has_valid_texdir")
        row.enabled = False
        row = layout.row()
        row.prop(self, "overwrite")
        row.enabled = self.has_valid_texdir

    def invoke(self, context, event):

        if self.parentpath.startswith("nb.voxelvolumes"):
            self.is_overlay = True

        if context.scene.nb.overlaytype == "labelgroups":
            self.is_label = True

        self.name = self.name
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class ImportScalarGroups(Operator, ImportHelper):
    bl_idname = "nb.import_scalargroups"
    bl_label = "Import time series overlay"
    bl_description = "Import time series overlay to vertexweights/colours"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="")
    texdir = StringProperty(
        name="Texture directory",
        description="Directory with textures for this scalargroup",
        default="",
        subtype="DIR_PATH")  # TODO

    def execute(self, context):
        filenames = [file.name for file in self.files]
        nb_imp.import_overlays(self.directory, filenames,
                               self.name, self.parentpath, "scalargroups")

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class ImportLabelGroups(Operator, ImportHelper):
    bl_idname = "nb.import_labelgroups"
    bl_label = "Import label overlay"
    bl_description = "Import label overlay to vertexgroups/colours"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="")

    def execute(self, context):
        filenames = [file.name for file in self.files]
        nb_imp.import_overlays(self.directory, filenames,
                               self.name, self.parentpath, "labelgroups")

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class ImportBorderGroups(Operator, ImportHelper):
    bl_idname = "nb.import_bordergroups"
    bl_label = "Import bordergroup overlay"
    bl_description = "Import bordergroup overlay to curves"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)

    name = StringProperty(
        name="Name",
        description="Specify a name for the object (default: filename)",
        default="")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="")

    def execute(self, context):
        filenames = [file.name for file in self.files]
        nb_imp.import_overlays(self.directory, filenames,
                               self.name, self.parentpath, "bordergroups")

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class RevertLabel(Operator):
    bl_idname = "nb.revert_label"
    bl_label = "Revert label"
    bl_description = "Revert changes to imported label colour/transparency"
    bl_options = {"REGISTER"}

    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")

    def execute(self, context):

        scn = bpy.context.scene
        nb = scn.nb

        item = eval(self.data_path)

        mat = bpy.data.materials[item.name]
        rgb = mat.node_tree.nodes["RGB"]
        rgb.outputs[0].default_value = item.colour
        trans = mat.node_tree.nodes["Transparency"]
        trans.outputs[0].default_value = item.colour[3]

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_it = nb_utils.active_nb_overlayitem()[0]
        self.data_path = nb_it.path_from_id()

        return self.execute(context)


class WeightPaintMode(Operator):
    bl_idname = "nb.wp_preview"
    bl_label = "wp_mode button"
    bl_description = "Go to weight paint mode for preview"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        scn = bpy.context.scene

        nb_ob = nb_utils.active_nb_object()[0]
        scn.objects.active = bpy.data.objects[nb_ob.name]

        bpy.ops.object.mode_set(mode="WEIGHT_PAINT")

        index_scalars_update_func()

        return {"FINISHED"}


class VertexWeight2VertexColors(Operator):
    bl_idname = "nb.vw2vc"
    bl_label = "VW to VC"
    bl_description = "Bake vertex group weights to vertex colours"
    bl_options = {"REGISTER"}

    itemname = StringProperty(
        name="Name",
        description="Specify the vertex group to bake",
        default="")
    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")
    index = IntProperty(
        name="index",
        description="index",
        default=-1)
    matname = StringProperty(
        name="Name",
        description="Specify the material to bake to",
        default="")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        nb_ob = eval('.'.join(self.data_path.split('.')[:2]))
        group = eval('.'.join(self.data_path.split('.')[:3]))
        ob = bpy.data.objects[nb_ob.name]

        vcs = ob.data.vertex_colors
        vc = vcs.new(name=self.itemname)
        ob.data.vertex_colors.active = vc

        if hasattr(group, 'scalars'):
            scalar = eval(self.data_path)
            vgs = [ob.vertex_groups[scalar.name]]
            ob = nb_mat.assign_vc(ob, vc, vgs)
            mat = ob.data.materials[self.matname]
            nodes = mat.node_tree.nodes
            nodes["Attribute"].attribute_name = self.itemname

        elif hasattr(group, 'labels'):
            vgs = [ob.vertex_groups[label.name] for label in group.labels]
            ob = nb_mat.assign_vc(ob, vc, vgs, group, colour=[0.5, 0.5, 0.5])

        bpy.ops.object.mode_set(mode="VERTEX_PAINT")

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_ob = nb_utils.active_nb_object()[0]
        nb_ov = nb_utils.active_nb_overlay()[0]
        nb_it = nb_utils.active_nb_overlayitem()[0]

        if hasattr(nb_ov, 'scalars'):
            self.index = nb_ov.index_scalars
        elif hasattr(nb_ov, 'labels'):
            self.index = nb_ov.index_labels

        self.data_path = nb_it.path_from_id()

        self.itemname = nb_it.name
        self.matname = nb_ov.name

        return self.execute(context)


class VertexWeight2UV(Operator, ExportHelper):
    bl_idname = "nb.vw2uv"
    bl_label = "Bake vertex weights"
    bl_description = "Bake vertex weights to texture (via vcol)"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    itemname = StringProperty(
        name="Name",
        description="Specify the vertex group to bake",
        default="")
    data_path = StringProperty(
        name="data path",
        description="Specify object data path",
        default="")
    index = IntProperty(
        name="index",
        description="index",
        default=-1)
    matname = StringProperty(
        name="Name",
        description="Specify the material name for the group",
        default="")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        nb_ob = eval('.'.join(self.data_path.split('.')[:2]))
        group = eval('.'.join(self.data_path.split('.')[:3]))

        # TODO: exit on no UVmap

        # prep directory
        if not bpy.data.is_saved:
            nb_utils.force_save(nb.projectdir)
        if not group.texdir:
            group.texdir = "//uvtex_%s" % group.name
        nb_utils.mkdir_p(bpy.path.abspath(group.texdir))

        # set the surface as active object
        surf = bpy.data.objects[nb_ob.name]
        for ob in bpy.data.objects:
            ob.select = False
        surf.select = True
        context.scene.objects.active = surf

        # save old and set new render settings for baking
        engine = scn.render.engine
        scn.render.engine = "CYCLES"
        samples = scn.cycles.samples
        preview_samples = scn.cycles.preview_samples
        scn.cycles.samples = 5
        scn.cycles.preview_samples = 5
        scn.cycles.bake_type = 'EMIT'

        # save old and set new materials for baking
        ami = surf.active_material_index
        matnames = [ms.name for ms in surf.material_slots]
        surf.data.materials.clear()
        img = self.create_baking_material(surf, nb.uv_resolution, "bake_vcol")

        # select the item(s) to bake
        dp_split = re.findall(r"[\w']+", self.data_path)
        items = eval("group.%s" % dp_split[-2])
        if not nb.uv_bakeall:
            items = [items[self.index]]

        # bake
        vcs = surf.data.vertex_colors
        for i, item in enumerate(items):
            dp = item.path_from_id()
            bpy.ops.nb.vw2vc(itemname=item.name, data_path=dp,
                             index=i, matname="bake_vcol")
            img.source = 'GENERATED'
            bpy.ops.object.bake()
            if len(items) > 1:
                itemname = item.name[-5:]
            else:
                itemname = item.name
            img.filepath_raw = os.path.join(group.texdir, itemname + ".png")
            img.save()
            vc = vcs[vcs.active_index]
            vcs.remove(vc)

        # reinstate materials and render settings
        surf.data.materials.pop(0)
        for matname in matnames:
            surf.data.materials.append(bpy.data.materials[matname])
        surf.active_material_index = ami
        scn.render.engine = engine
        scn.cycles.samples = samples
        scn.cycles.preview_samples = preview_samples

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_ob = nb_utils.active_nb_object()[0]
        nb_ov = nb_utils.active_nb_overlay()[0]
        nb_it = nb_utils.active_nb_overlayitem()[0]

        if hasattr(nb_ov, 'scalars'):
            self.index = nb_ov.index_scalars
        elif hasattr(nb_ov, 'labels'):
            self.index = nb_ov.index_labels
        self.data_path = nb_it.path_from_id()
        self.itemname = nb_it.name
        self.matname = nb_ov.name

        return self.execute(context)

    def create_baking_material(self, surf, uvres, name):
        """Create a material to bake vertex colours to."""

        mat = nb_mat.make_material_bake_cycles(name)
        surf.data.materials.append(mat)

        nodes = mat.node_tree.nodes
        itex = nodes['Image Texture']
        attr = nodes['Attribute']
        out = nodes['Material Output']

        img = bpy.data.images.new(name, width=uvres, height=uvres)
        img.file_format = 'PNG'
        img.source = 'GENERATED'
        itex.image = img
        attr.attribute_name = name

        for node in nodes:
            node.select = False
        out.select = True
        nodes.active = out

        return img

class UnwrapSurface(Operator):
    bl_idname = "nb.unwrap_surface"
    bl_label = "Unwrap surface"
    bl_description = "Unwrap a surface with sphere projection"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name_surface = StringProperty(
        name="Surface name",
        description="Specify the name for the surface to unwrap",
        default="")
    name_sphere = StringProperty(
        name="Sphere name",
        description="Specify the name for the sphere object to unwrap from",
        default="")

    def execute(self, context):

        scn = context.scene

        surf = bpy.data.objects[self.name_surface]
        sphere = bpy.data.objects[self.name_sphere]

        # select sphere and project
        for ob in bpy.data.objects:
            ob.select = False
        sphere.select = True
        scn.objects.active = sphere
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.sphere_project()
        bpy.ops.object.mode_set(mode='OBJECT')
        # TODO: perhaps do scaling here to keep all vertices within range

        # copy the UV map: select surf then sphere
        surf.select = True
        scn.objects.active = sphere
        bpy.ops.object.join_uvs()

        return {"FINISHED"}

    def invoke(self, context, event):

        nb_ob = nb_utils.active_nb_object()[0]
        self.name_surface = nb_ob.name
        self.name_sphere = nb_ob.sphere

        return self.execute(context)


class NeuroBlenderScenePanel(Panel):
    """Host the NeuroBlender scene setup functionality"""
    bl_idname = "OBJECT_PT_nb_scene"
    bl_label = "NeuroBlender - Scene setup"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    draw = NeuroBlenderBasePanel.draw
    drawunit_switch_to_main = NeuroBlenderBasePanel.drawunit_switch_to_main
    drawunit_UIList = NeuroBlenderBasePanel.drawunit_UIList
    drawunit_tri = NeuroBlenderBasePanel.drawunit_tri
    drawunit_basic_cycles = NeuroBlenderBasePanel.drawunit_basic_cycles
    drawunit_basic_cycles_mix = NeuroBlenderBasePanel.drawunit_basic_cycles_mix

    def draw_nb_panel(self, layout, nb):

        self.drawunit_presets(layout, nb)

        try:
            idx = nb.index_presets
            preset = nb.presets[idx]
        except IndexError:
            pass
        else:
            row = layout.row()
            row.prop(preset, "name")

            row = layout.row()
            row.separator()

            self.drawunit_tri(layout, "bounds", nb, preset)
            self.drawunit_tri(layout, "cameras", nb, preset)
            self.drawunit_tri(layout, "lights", nb, preset)
            self.drawunit_tri(layout, "tables", nb, preset)

        row = layout.row()
        row.separator()
        obs = [ob for ob in bpy.data.objects
               if ob.type not in ["CAMERA", "LAMP", "EMPTY"]]
        sobs = bpy.context.selected_objects
        if obs:
            row = layout.row()
            row.operator("nb.scene_preset",
                         text="Load scene preset",
                         icon="WORLD")
            row.enabled = len(nb.presets) > 0
        else:
            row = layout.row()
            row.label(text="No geometry loaded ...")

    def drawunit_presets(self, layout, nb):

        row = layout.row()
        row.operator("nb.add_preset", icon='ZOOMIN', text="")
        row.prop(nb, "presets_enum", expand=False, text="")
        row.operator("nb.del_preset", icon='ZOOMOUT', text="")

    def drawunit_tri_bounds(self, layout, nb, preset):

        preset_ob = bpy.data.objects[preset.centre]
        row = layout.row()
        col = row.column()
        col.prop(preset_ob, "location")
        col = row.column()
        col.operator("nb.reset_presetcentre", icon='BACK', text="")

        col = row.column()
        col.prop(preset_ob, "scale")
#         col.prop(preset, "dims")
#         col.enabled = False
        col = row.column()
        col.operator("nb.reset_presetdims", icon='BACK', text="")

    def drawunit_tri_cameras(self, layout, nb, preset):

        try:
            cam = preset.cameras[0]
        except IndexError:
            cam = preset.cameras.add()
            preset.index_cameras = (len(preset.cameras)-1)
        else:
            cam_ob = bpy.data.objects[cam.name]

            row = layout.row()

            split = row.split(percentage=0.55)
            col = split.column(align=True)
            col.label("Quick camera view:")
            row1 = col.row(align=True)
            row1.prop(cam, "cam_view_enum_LR", expand=True)
            row1 = col.row(align=True)
            row1.prop(cam, "cam_view_enum_AP", expand=True)
            row1 = col.row(align=True)
            row1.prop(cam, "cam_view_enum_IS", expand=True)

            col.prop(cam, "cam_distance", text="distance")

            split = split.split(percentage=0.1)
            col = split.column()
            col.separator()

            col = split.column(align=True)
            col.prop(cam_ob, "location", index=-1)

            row = layout.row()
            row.separator()

            row = layout.row()

            split = row.split(percentage=0.55)
            col = split.column(align=True)
            col.label(text="Track object:")
            col.prop(cam, "trackobject", text="")
            if cam.trackobject == "None":
                col.prop(cam_ob, "rotation_euler", index=2, text="tumble")

            split = split.split(percentage=0.1)
            col = split.column()
            col.separator()

            camdata = cam_ob.data
            col = split.column(align=True)
            col.label(text="Clipping:")
            col.prop(camdata, "clip_start", text="Start")
            col.prop(camdata, "clip_end", text="End")

#             split = layout.split(percentage=0.66)
# 
#             camdata = cam_ob.data
#             row = split.row(align=True)
#             row.prop(camdata, "clip_start")
#             row.prop(camdata, "clip_end")
# 
#             if cam.trackobject == "None":
#                 split.prop(cam_ob, "rotation_euler", index=2, text="tumble")

    def drawunit_tri_lights(self, layout, nb, preset):

        lights = bpy.data.objects[preset.lightsempty]
        row = layout.row(align=True)
        col = row.column(align=True)
        col.prop(lights, "rotation_euler", index=2, text="Rotate rig (Z)")
        col = row.column(align=True)
        col.prop(lights, "scale", index=2, text="Scale rig (XYZ)")

        row = layout.row()
        row.separator()

        self.drawunit_UIList(layout, "PL", preset, "lights", addopt=True)
        self.drawunit_lightprops(layout, preset.lights[preset.index_lights])

    def drawunit_lightprops(self, layout, light):

        light_ob = bpy.data.objects[light.name]

        row = layout.row()

        split = row.split(percentage=0.55)
        col = split.column(align=True)
        col.label("Quick access:")
        col.prop(light, "type", text="")
        col.prop(light, "strength")
        if light.type == "PLANE":
            row = col.row(align=True)
            row.prop(light, "size", text="")

        split = split.split(percentage=0.1)
        col = split.column()
        col.separator()

        col = split.column(align=True)
        col.prop(light_ob, "location")

    def drawunit_tri_tables(self, layout, nb, preset):

        try:
            tab = preset.tables[0]
        except IndexError:
            # tab = nb_rp.create_table(preset.name+"DissectionTable")
            tab = preset.tables.add()
            preset.index_tables = (len(preset.tables)-1)
        else:
            row = layout.row()
            row.prop(tab, "is_rendered", toggle=True)
            row = layout.row()
            self.drawunit_basic_cycles(layout, tab)


class ResetPresetCentre(Operator):
    bl_idname = "nb.reset_presetcentre"
    bl_label = "Reset preset centre"
    bl_description = "Revert location changes to preset centre"
    bl_options = {"REGISTER"}

    def execute(self, context):

        scn = bpy.context.scene
        nb = scn.nb

        obs = nb_rp.get_render_objects(nb)
        centre_location = nb_rp.get_brainbounds(obs)[0]

        nb_preset = nb.presets[nb.index_presets]
        name = nb_preset.centre
        centre = bpy.data.objects[name]
        centre.location = centre_location

        infostring = 'reset location of preset "%s"'
        info = [infostring % nb_preset.name]
        infostring = 'location is now "%s"'
        info += [infostring % ' '.join('%.2f' % l for l in centre_location)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}


class ResetPresetDims(Operator):
    bl_idname = "nb.reset_presetdims"
    bl_label = "Recalculate scene dimensions"
    bl_description = "Recalculate scene dimension"
    bl_options = {"REGISTER"}

    def execute(self, context):

        scn = bpy.context.scene
        nb = scn.nb

        obs = nb_rp.get_render_objects(nb)
        dims = nb_rp.get_brainbounds(obs)[1]

        nb_preset = nb.presets[nb.index_presets]
        name = nb_preset.centre
        centre = bpy.data.objects[name]
        centre.scale = 0.5 * mathutils.Vector(dims)

        nb.presets[nb.index_presets].dims = dims

        infostring = 'reset dimensions of preset "%s"'
        info = [infostring % nb_preset.name]
        infostring = 'dimensions are now "%s"'
        info += [infostring % ' '.join('%.2f' % d for d in dims)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}


class AddPreset(Operator):
    bl_idname = "nb.add_preset"
    bl_label = "New preset"
    bl_description = "Create a new preset"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the preset",
        default="Preset")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        ca = [nb.presets]
        name = nb_utils.check_name(self.name, "", ca, firstfill=1)

        nb_rp.scene_preset_init(name)
        nb.presets_enum = name

        infostring = 'added preset "%s"'
        info = [infostring % name]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}


class DelPreset(Operator):
    bl_idname = "nb.del_preset"
    bl_label = "Delete preset"
    bl_description = "Delete a preset"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the preset",
        default="")
    index = IntProperty(
        name="index",
        description="Specify preset index",
        default=-1)

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        info = []

        if self.name:  # got here through cli
            try:
                nb.presets[self.name]
            except KeyError:
                infostring = 'no preset with name "%s"'
                info = [infostring % self.name]
                self.report({'INFO'}, info[0])
                return {"CANCELLED"}
            else:
                self.index = nb.presets.find(self.name)
        else:  # got here through invoke
            self.name = nb.presets[self.index].name

        info = self.delete_preset(nb.presets[self.index], info)
        nb.presets.remove(self.index)
        nb.index_presets -= 1
        infostring = 'removed preset "%s"'
        info = [infostring % self.name] + info

        try:
            name = nb.presets[0].name
        except IndexError:
            infostring = 'all presets have been removed'
            info += [infostring]
        else:
            nb.presets_enum = name
            infostring = 'preset is now "%s"'
            info += [infostring % name]

        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index = nb.index_presets
        self.name = ""

        return self.execute(context)

    def delete_preset(self, nb_preset, info=[]):
        """Delete a preset."""

        # unlink all objects from the rendering scenes
        for s in ['_cycles', '_internal']:
            sname = nb_preset.name + s
            try:
                scn = bpy.data.scenes[sname]
            except KeyError:
                infostring = 'scene "%s" not found'
                info += [infostring % sname]
            else:
                for ob in scn.objects:
                    scn.objects.unlink(ob)
                bpy.data.scenes.remove(scn)

        # delete all preset objects and data
        ps_obnames = [nb_ob.name
                      for nb_coll in [nb_preset.cameras,
                                      nb_preset.lights,
                                      nb_preset.tables]
                      for nb_ob in nb_coll]
        ps_obnames += [nb_preset.lightsempty,
                       nb_preset.box,
                       nb_preset.centre,
                       nb_preset.name]
        for ps_obname in ps_obnames:
            try:
                ob = bpy.data.objects[ps_obname]
            except KeyError:
                infostring = 'object "%s" not found'
                info += [infostring % ps_obname]
            else:
                bpy.data.objects.remove(ob)

        for ps_cam in nb_preset.cameras:
            try:
                cam = bpy.data.cameras[ps_cam.name]
            except KeyError:
                infostring = 'camera "%s" not found'
                info += [infostring % ps_cam.name]
            else:
                bpy.data.cameras.remove(cam)

        for ps_lamp in nb_preset.lights:
            try:
                lamp = bpy.data.lamps[ps_lamp.name]
            except KeyError:
                infostring = 'lamp "%s" not found'
                info += [infostring % ps_lamp.name]
            else:
                bpy.data.lamps.remove(lamp)

        for ps_mesh in nb_preset.tables:
            try:
                mesh = bpy.data.meshes[ps_mesh.name]
            except KeyError:
                infostring = 'mesh "%s" not found'
                info += [infostring % ps_mesh.name]
            else:
                bpy.data.meshes.remove(mesh)

        # TODO:
        # delete animations from objects
        # delete colourbars
        # delete campaths?

        return info


class AddLight(Operator):
    bl_idname = "nb.import_lights"
    bl_label = "New light"
    bl_description = "Create a new light"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    index = IntProperty(
        name="index",
        description="Specify preset index",
        default=-1)
    name = StringProperty(
        name="Name",
        description="Specify a name for the light",
        default="Light")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")
    type = EnumProperty(
        name="Light type",
        description="type of lighting",
        items=[("PLANE", "PLANE", "PLANE", 1),
               ("POINT", "POINT", "POINT", 2),
               ("SUN", "SUN", "SUN", 3),
               ("SPOT", "SPOT", "SPOT", 4),
               ("HEMI", "HEMI", "HEMI", 5),
               ("AREA", "AREA", "AREA", 6)],
        default="SPOT")
    colour = FloatVectorProperty(
        name="Colour",
        description="Colour of the light",
        default=[1.0, 1.0, 1.0],
        subtype="COLOR")
    strength = FloatProperty(
        name="Strength",
        description="Strength of the light",
        default=1,
        min=0)
    size = FloatVectorProperty(
        name="Size",
        description="Relative size of the plane light (to bounding box)",
        size=2,
        default=[1.0, 1.0])
    location = FloatVectorProperty(
        name="Location",
        description="",
        default=[3.88675, 2.88675, 2.88675],
        size=3,
        subtype="TRANSLATION")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        nb_preset = nb.presets[self.index]
        preset = bpy.data.objects[nb_preset.name]
        centre = bpy.data.objects[nb_preset.centre]
        box = bpy.data.objects[nb_preset.box]
        lights = bpy.data.objects[nb_preset.lightsempty]

        ca = [nb_preset.lights]
        name = nb_utils.check_name(self.name, "", ca)

        lp = {'name': name,
              'type': self.type,
              'size': self.size,
              'colour': self.colour,
              'strength': self.strength,
              'location': self.location}
        nb_light = nb_utils.add_item(nb_preset, "lights", lp)
        nb_rp.create_light(preset, centre, box, lights, lp)

        infostring = 'added light "%s" in preset "%s"'
        info = [infostring % (name, nb_preset.name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index = nb.index_presets

        return self.execute(context)

class ScenePreset(Operator):
    bl_idname = "nb.scene_preset"
    bl_label = "Load scene preset"
    bl_description = "Setup up camera and lighting for this brain"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        nb_rp.scene_preset()

        return {"FINISHED"}


class SetAnimations(Operator):
    bl_idname = "nb.set_animations"
    bl_label = "Set animations"
    bl_description = "(Re)set all animation in the preset"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):

        nb_rp.set_animations()

        return {"FINISHED"}


class NeuroBlenderAnimationPanel(Panel):
    """Host the NeuroBlender animation functionality"""
    bl_idname = "OBJECT_PT_nb_animation"
    bl_label = "NeuroBlender - Animations"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    draw = NeuroBlenderBasePanel.draw
    drawunit_switch_to_main = NeuroBlenderBasePanel.drawunit_switch_to_main
    drawunit_UIList = NeuroBlenderBasePanel.drawunit_UIList
    drawunit_tri = NeuroBlenderBasePanel.drawunit_tri

    def draw_nb_panel(self, layout, nb):

        try:
            idx = nb.index_presets
            preset = nb.presets[idx]
        except IndexError:
            row = layout.row()
            row.label(text="No presets loaded ...")
        else:
            self.drawunit_animations(layout, nb, preset)

        row = layout.row()
        row.operator("nb.set_animations",
                     text="Set animations",
                     icon="RENDER_ANIMATION")

    def drawunit_animations(self, layout, nb, preset):

        row = layout.row(align=True)
        row.prop(bpy.context.scene, "frame_start")
        row.prop(bpy.context.scene, "frame_end")

        row = layout.row()
        self.drawunit_UIList(layout, "AN", preset, "animations")

        try:
            anim = preset.animations[preset.index_animations]
        except IndexError:
            pass
        else:
            row = layout.row()
            row.separator()

            row = layout.row()
            row.prop(anim, "animationtype", expand=True)

            row = layout.row()
            row.separator()

            self.drawunit_tri(layout, "timings", nb, preset)

#             funstring = 'self.drawunit_tri(layout, "anim{}", nb, preset)'
            funstring = 'self.drawunit_animation_{}(layout, nb, preset)'
            fun = funstring.format(anim.animationtype.lower())
            eval(fun)

    def drawunit_tri_timings(self, layout, nb, preset):

        self.drawunit_animation_timings(layout, nb, preset)

    def drawunit_animation_timings(self, layout, nb, preset):

        anim = preset.animations[preset.index_animations]

        row = layout.row(align=True)
        row.prop(anim, "frame_start")
        row.prop(anim, "frame_end")

        row = layout.row(align=True)
        row.prop(anim, "repetitions")
        row.prop(anim, "offset")

    def drawunit_animation_camerapath(self, layout, nb, preset):

        self.drawunit_tri(layout, "camerapath", nb, preset)
        self.drawunit_tri(layout, "tracking", nb, preset)

    def drawunit_tri_camerapath(self, layout, nb, preset):

        self.drawunit_camerapath(layout, nb, preset)

    def drawunit_camerapath(self, layout, nb, preset):

        anim = preset.animations[preset.index_animations]
# 
        row = layout.row()
        col = row.column()
        col.prop(anim, "reverse", toggle=True,
                 icon="ARROW_LEFTRIGHT", icon_only=True)
        col = row.column()
        col.prop(anim, "campaths_enum", expand=False, text="")
        col = row.column()
        col.operator("nb.del_campath", icon='ZOOMOUT', text="")
        col.enabled = True

        box = layout.box()
        self.drawunit_tri(box, "newpath", nb, anim)
        if anim.campaths_enum:
            self.drawunit_tri(box, "points", nb, anim)

    def drawunit_tri_tracking(self, layout, nb, preset):

        self.drawunit_tracking(layout, nb, preset)

    def drawunit_tracking(self, layout, nb, preset):

        anim = preset.animations[preset.index_animations]

        nb_cam = preset.cameras[0]
        cam_ob = bpy.data.objects[nb_cam.name]
        cam = bpy.data.cameras[nb_cam.name]

        row = layout.row()
        row.prop(anim, "tracktype", expand=True)

        split = layout.split(percentage=0.33)
        split.prop(cam_ob, "rotation_euler", index=2, text="tumble")

        row = split.row(align=True)
        row.prop(cam, "clip_start")
        row.prop(cam, "clip_end")

    def drawunit_tri_points(self, layout, nb, anim):

        row = layout.row()
        row.operator("nb.add_campoint",
                     text="Add point at camera position")

        try:
            cu = bpy.data.objects[anim.campaths_enum].data
            data = cu.splines[0]
        except:
            pass
        else:
            if len(data.bezier_points):
                ps = "bezier_points"
            else:
                ps = "points"

            row = layout.row()
            row.template_list("ObjectListCP", "",
                              data, ps,
                              data, "material_index", rows=2,
                              maxrows=4, type="DEFAULT")

    def drawunit_tri_newpath(self, layout, nb, anim):

        row = layout.row()
        row.prop(anim, "pathtype", expand=True)

        row = layout.row()
        if anim.pathtype == 'Circular':
            row = layout.row()
            row.prop(anim, "axis", expand=True)
        elif anim.pathtype == 'Streamline':
            row = layout.row()
            row.prop(anim, "anim_tract", text="")
            row.prop(anim, "spline_index")
        elif anim.pathtype == 'Select':
            row = layout.row()
            row.prop(anim, "anim_curve", text="")
        elif anim.pathtype == 'Create':
            pass  # name, for every options?

        row = layout.row()
        row.separator()

        row = layout.row()
        row.operator("nb.add_campath", text="Add trajectory")

    def drawunit_animation_slices(self, layout, nb, preset):

        self.drawunit_tri(layout, "animslices", nb, preset)

    def drawunit_tri_animslices(self, layout, nb, preset):

        anim = preset.animations[preset.index_animations]

        row = layout.row()
        col = row.column()
        col.prop(anim, "reverse", toggle=True,
                 icon="ARROW_LEFTRIGHT", icon_only=True)
        col = row.column()
        col.prop(anim, "anim_voxelvolume", expand=False, text="")
        col = row.column()
        col.operator("nb.del_campath", icon='ZOOMOUT', text="")
        col.enabled = False

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(anim, "sliceproperty", expand=True)

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(anim, "axis", expand=True)

    def drawunit_animation_timeseries(self, layout, nb, preset):

        self.drawunit_tri(layout, "timeseries", nb, preset)

    def drawunit_tri_timeseries(self, layout, nb, preset):

        anim = preset.animations[preset.index_animations]

        row = layout.row()
        col = row.column()
        col.prop(anim, "timeseries_object", expand=False,
                 text="Object")

        row = layout.row()
        col = row.column()
        col.prop(anim, "anim_timeseries", expand=False,
                 text="Time series")

        # FIXME: gives many errors on adding campath???
#         sgs = nb_rp.find_ts_scalargroups(anim)
#         sg = sgs[anim.anim_timeseries]
# 
#         npoints = len(sg.scalars)
#         row = layout.row()
#         row.label("%d points in time series" % npoints)


class AddAnimation(Operator):
    bl_idname = "nb.import_animations"
    bl_label = "New animation"
    bl_description = "Create a new animation"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    index_presets = IntProperty(
        name="index presets",
        description="Specify preset index",
        default=-1)
    name = StringProperty(
        name="Name",
        description="Specify a name for the animation",
        default="Anim")
    parentpath = StringProperty(
        name="Parentpath",
        description="The path to the parent of the object",
        default="nb")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        ca = [preset.animations for preset in nb.presets]
        name = nb_utils.check_name(self.name, "", ca, forcefill=True)
        nb_imp.add_animation_to_collection(name)

        nb_preset = nb.presets[nb.index_presets]  # FIXME: self
        infostring = 'added animation "%s" in preset "%s"'
        info = [infostring % (name, nb_preset.name)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets

        return self.execute(context)


class AddCamPoint(Operator):
    bl_idname = "nb.add_campoint"
    bl_label = "New camera position"
    bl_description = "Create a new camera position in campath"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    index_presets = IntProperty(
        name="index presets",
        description="Specify preset index",
        default=-1)
    index_animations = IntProperty(
        name="index animations",
        description="Specify animation index",
        default=-1)
    co = FloatVectorProperty(
        name="camera coordinates",
        description="Specify camera coordinates",
        default=[0.0, 0.0, 0.0])

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        preset = nb.presets[self.index_presets]
        anim = preset.animations[self.index_animations]
        campath = bpy.data.objects[anim.campaths_enum]

        try:
            spline = campath.data.splines[0]
            spline.points.add()
        except:
            spline = campath.data.splines.new('POLY')

        spline.points[-1].co = tuple(self.co) + (1,)
        spline.order_u = len(spline.points) - 1
        spline.use_endpoint_u = True

        infostring = 'added campoint "%02f, %02f, %02f"'
        info = [infostring % tuple(self.co)]
        self.report({'INFO'}, '; '.join(info))

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets
        preset = nb.presets[self.index_presets]

        self.index_animations = preset.index_animations

        cam = bpy.data.objects[preset.cameras[0].name]
        centre = bpy.data.objects[preset.centre]

        self.co[0] = cam.location[0] * preset.dims[0] / 2 + centre.location[0]
        self.co[1] = cam.location[1] * preset.dims[1] / 2 + centre.location[1]
        self.co[2] = cam.location[2] * preset.dims[2] / 2 + centre.location[2]

        return self.execute(context)


class AddCamPath(Operator):
    bl_idname = "nb.add_campath"
    bl_label = "New camera path"
    bl_description = "Create a new path for the camera"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the camera path",
        default="")
    index_presets = IntProperty(
        name="index",
        description="Specify preset index",
        default=-1)
    index_animations = IntProperty(
        name="index animations",
        description="Specify animation index",
        default=-1)
    pathtype = EnumProperty(
        name="Pathtype",
        description="Trajectory types for the camera animation",
        items=[("Circular", "Circular",
                "Circular trajectory from camera position", 0),
               ("Streamline", "Streamline",
                "Curvilinear trajectory from a streamline", 1),
               ("Select", "Select",
                "Curvilinear trajectory from curve", 2),
               ("Create", "Create",
                "Create a path from camera positions", 3)],
        default="Circular")
    axis = EnumProperty(
        name="Animation axis",
        description="switch between animation axes",
        items=[("X", "X", "X", 0),
               ("Y", "Y", "Y", 1),
               ("Z", "Z", "Z", 2)],
        default="Z")
    anim_tract = StringProperty(
        name="Animation streamline",
        description="Tract to animate",
        default="")
    spline_index = IntProperty(
        name="streamline index",
        description="index of the streamline to animate",
        min=0,
        default=0)
    anim_curve = StringProperty(
        name="Animation curves",
        description="Curve to animate",
        default="")

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        preset = nb.presets[self.index_presets]
        anim = preset.animations[self.index_animations]

        if self.pathtype == "Circular":
            name = "CP_%s" % (self.axis)
        elif self.pathtype == "Streamline":
            name = "CP_%s_%05d" % (self.anim_tract, self.spline_index)
        elif self.pathtype == "Select":
            name = "CP_%s" % (anim.anim_curve)
        elif self.pathtype == "Create":
            name = "CP_%s" % ("fromCam")

        ca = [nb.campaths]
        name = self.name or name
        name = nb_utils.check_name(name, "", ca)
        fun = eval("self.campath_%s" % self.pathtype.lower())
        campath, info = fun(name)

        if campath is not None:
            campath.hide_render = True
            campath.parent = bpy.data.objects[preset.name]
            nb_imp.add_campath_to_collection(name)
            infostring = 'added camera path "%s" to preset "%s"'
            info = [infostring % (name, preset.name)] + info

            infostring = 'switched "%s" camera path to "%s"'
            info += [infostring % (anim.name, campath.name)]
            anim.campaths_enum = campath.name
            status = "FINISHED"
        else:
            status = "CANCELLED"

        self.report({'INFO'}, '; '.join(info))

        return {status}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets
        preset = nb.presets[self.index_presets]
        self.index_animations = preset.index_animations
        anim = preset.animations[self.index_animations]
        self.pathtype = anim.pathtype
        self.axis = anim.axis
        self.anim_tract = anim.anim_tract
        self.spline_index = anim.spline_index
        self.anim_curve = anim.anim_curve

        return self.execute(context)

    def campath_circular(self, name):
        """Generate a circular trajectory from the camera position."""

        scn = bpy.context.scene
        nb = scn.nb

        preset = nb.presets[self.index_presets]
        cam = bpy.data.objects[preset.cameras[0].name]
        centre = bpy.data.objects[preset.centre]
        box = bpy.data.objects[preset.box]

        camview = cam.location * box.matrix_world

        if 'X' in self.axis:
            idx = 0
            rotation_offset = np.arctan2(camview[2], camview[1])
            r = np.sqrt(camview[1]**2 + camview[2]**2)
            r = max(0.001, r)
            h = 0.55 * r
            coords = [((0, 0, r), (0, h, r), (0, -h, r)),
                      ((0, -r, 0), (0, -r, h), (0, -r, -h)),
                      ((0, 0, -r), (0, -h, -r), (0, h, -r)),
                      ((0, r, 0), (0, r, -h), (0, r, h))]
        elif 'Y' in self.axis:
            idx = 1
            rotation_offset = np.arctan2(camview[0], camview[2])
            r = np.sqrt(camview[0]**2 + camview[2]**2)
            r = max(0.001, r)
            h = 0.55 * r
            coords = [((0, 0, r), (h, 0, r), (-h, 0, r)),
                      ((-r, 0, 0), (-r, 0, h), (-r, 0, -h)),
                      ((0, 0, -r), (-h, 0, -r), (h, 0, -r)),
                      ((r, 0, 0), (r, 0, -h), (r, 0, h))]
        elif 'Z' in self.axis:
            idx = 2
            rotation_offset = np.arctan2(camview[1], camview[0])
            r = np.sqrt(camview[0]**2 + camview[1]**2)
            r = max(0.001, r)
            h = 0.55 * r
            coords = [((0, r, 0), (h, r, 0), (-h, r, 0)),
                      ((-r, 0, 0), (-r, h, 0), (-r, -h, 0)),
                      ((0, -r, 0), (-h, -r, 0), (h, -r, 0)),
                      ((r, 0, 0), (r, -h, 0), (r, h, 0))]

        ob = self.create_circle(name, coords=coords)

        ob.rotation_euler[idx] = rotation_offset
        ob.location = centre.location
        ob.location[idx] = camview[idx] + centre.location[idx]

        origin = mathutils.Vector(coords[0][0]) + centre.location
        o = "%s" % ', '.join('%.2f' % co for co in origin)
        infostring = 'created path around %s with radius %.2f starting at [%s]'
        info = [infostring % (self.axis, r, o)]

        return ob, info

    def campath_streamline(self, name):
        """Generate a curvilinear trajectory from a streamline."""

        scn = bpy.context.scene

        try:
            nb_ob = bpy.data.objects[self.anim_tract]
            spline = nb_ob.data.splines[self.spline_index]
        except KeyError:
            ob = None
            infostring = 'tract "%s:spline[%s]" not found'
        except IndexError:
            ob = None
            infostring = 'streamline "%s:spline[%s]" not found'
        else:
            curve = bpy.data.curves.new(name=name, type='CURVE')
            curve.dimensions = '3D'
            ob = bpy.data.objects.new(name, curve)
            scn.objects.link(ob)

            streamline = [point.co[0:3] for point in spline.points]
            nb_imp.make_polyline_ob(curve, streamline)
            ob.matrix_world = nb_ob.matrix_world
            ob.select = True
            bpy.context.scene.objects.active = ob
            bpy.ops.object.transform_apply(location=False,
                                           rotation=False,
                                           scale=True)

            infostring = 'copied path from tract "%s:spline[%s]"'

        info = [infostring % (self.anim_tract, self.spline_index)]

        return ob, info

    def campath_select(self, name):
        """Generate a campath by copying it from a curve object."""

        scn = bpy.context.scene

        try:
            cubase = bpy.data.objects[self.anim_curve]
        except KeyError:
            ob = None
            infostring = 'curve "%s" not found'
        else:
            cu = cubase.data.copy()
            cu.name = name
            ob = bpy.data.objects.new(name, cu)
            scn.objects.link(ob)
            scn.update()
            ob.matrix_world = cubase.matrix_world
            ob.select = True
            bpy.context.scene.objects.active = ob
            bpy.ops.object.transform_apply(location=False,
                                           rotation=False,
                                           scale=True)
            infostring = 'copied camera path from "%s"'

        info = [infostring % self.anim_curve]

        return ob, info

    def campath_create(self, name):
        """Generate an empty trajectory."""

        scn = bpy.context.scene

        curve = bpy.data.curves.new(name=name, type='CURVE')
        curve.dimensions = '3D'
        ob = bpy.data.objects.new(name, curve)
        scn.objects.link(ob)

        infostring = 'created empty path'

        info = [infostring]

        return ob, info

    def create_circle(self, name, coords):
        """Create a bezier circle from a list of coordinates."""

        scn = bpy.context.scene

        cu = bpy.data.curves.new(name, type='CURVE')
        cu.dimensions = '3D'
        ob = bpy.data.objects.new(name, cu)
        scn.objects.link(ob)
        scn.objects.active = ob
        ob.select = True

        polyline = cu.splines.new('BEZIER')
        polyline.bezier_points.add(len(coords) - 1)
        for i, coord in enumerate(coords):
            polyline.bezier_points[i].co = coord[0]
            polyline.bezier_points[i].handle_left = coord[1]
            polyline.bezier_points[i].handle_right = coord[2]

        polyline.use_cyclic_u = True

        return ob


class DelCamPath(Operator):
    bl_idname = "nb.del_campath"
    bl_label = "Delete camera path"
    bl_description = "Delete a camera path"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="Name",
        description="Specify a name for the camera path",
        default="")
    index_presets = IntProperty(
        name="index",
        description="Specify preset index",
        default=-1)
    index_animations = IntProperty(
        name="index animations",
        description="Specify animation index",
        default=-1)

    def execute(self, context):

        scn = context.scene
        nb = scn.nb

        try:
            campath = bpy.data.objects[self.name]
            cu = bpy.data.curves[self.name]
        except KeyError:
            infostring = 'camera path curve "%s" not found'
        else:
            bpy.data.curves.remove(cu)
            bpy.data.objects.remove(campath)
            nb.campaths.remove(nb.campaths.find(self.name))
            nb.index_campaths = 0
            # TODO: find and reset all animations that use campath
            infostring = 'removed camera path curve "%s"'

        info = [infostring % self.name]

        return {"FINISHED"}

    def invoke(self, context, event):

        scn = context.scene
        nb = scn.nb

        self.index_presets = nb.index_presets
        preset = nb.presets[self.index_presets]
        self.index_animations = preset.index_animations
        anim = preset.animations[self.index_animations]
        self.name = anim.campaths_enum

        return self.execute(context)


class NeuroBlenderSettingsPanel(Panel):
    """Host the NeuroBlender settings"""
    bl_idname = "OBJECT_PT_nb_settings"
    bl_label = "NeuroBlender - Settings"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    draw = NeuroBlenderBasePanel.draw
    drawunit_switch_to_main = NeuroBlenderBasePanel.drawunit_switch_to_main

    def draw_nb_panel(self, layout, nb):

        row = layout.row(align=True)
        row.menu(OBJECT_MT_setting_presets.__name__,
                 text=OBJECT_MT_setting_presets.bl_label)
        row.operator(AddPresetSettingsDraw.bl_idname,
                     text="", icon='ZOOMIN')
        row.operator(AddPresetSettingsDraw.bl_idname,
                     text="", icon='ZOOMOUT').remove_active = True

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(nb, "projectdir")

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(nb, "esp_path")

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(nb, "mode", expand=True)

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(nb, "engine", expand=True)

        row = layout.row()
        row.separator()

        box = layout.box()
        row = box.row()
        row.prop(nb, "texformat")
        row = box.row()
        row.prop(nb, "texmethod")
        row = box.row()
        row.prop(nb, "uv_resolution")

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(nb, "advanced", toggle=True,
                 text="Expanded options")

        row = layout.row()
        row.separator()

        row = layout.row()
        row.prop(nb, "verbose", toggle=True,
                 text="Verbose reporting")

        row = layout.row()
        row.separator()

        row = layout.row()
        row.operator("nb.reload",
                     text="Reload NeuroBlender",
                     icon="RECOVER_LAST")


# https://docs.blender.org/api/blender_python_api_2_77_0/bpy.types.Menu.html
class OBJECT_MT_setting_presets(Menu):
    bl_label = "Setting Presets"
    preset_subdir = "neuroblender"
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset


class AddPresetSettingsDraw(AddPresetBase, Operator):
    bl_idname = "nb.setting_presets"
    bl_label = "NeuroBlender setting presets"
    preset_menu = "OBJECT_MT_setting_presets"

    preset_defines = ["scn = bpy.context.scene"]
    preset_values = ["scn.nb.projectdir",
                     "scn.nb.esp_path",
                     "scn.nb.mode",
                     "scn.nb.engine",
                     "scn.nb.texformat",
                     "scn.nb.texmethod",
                     "scn.nb.uv_resolution",
                     "scn.nb.advanced",
                     "scn.nb.verbose"]
    preset_subdir = "neuroblender"


class SwitchToMainScene(Operator):
    bl_idname = "nb.switch_to_main"
    bl_label = "Switch to main"
    bl_description = "Switch to main NeuroBlender scene to import"
    bl_options = {"REGISTER"}

    def execute(self, context):

        context.window.screen.scene = bpy.data.scenes["Scene"]

        return {"FINISHED"}


class SaveBlend(Operator, ExportHelper):
    bl_idname = "nb.save_blend"
    bl_label = "Save blend file"
    bl_description = "Prompt to save a blend file"
    bl_options = {"REGISTER"}

    directory = StringProperty(subtype="FILE_PATH")
    files = CollectionProperty(name="Filepath",
                               type=OperatorFileListElement)
    filename_ext = StringProperty(subtype="NONE")

    def execute(self, context):

        bpy.ops.wm.save_as_mainfile(filepath=self.properties.filepath)

        return {"FINISHED"}

    def invoke(self, context, event):

        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}

class Reload(Operator):
    bl_idname = "nb.reload"
    bl_label = "Reload"
    bl_description = "Reload"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    name = StringProperty(
        name="name",
        description="The name of the addon",
        default="NeuroBlender")
    path = StringProperty(
        name="path",
        description="The path to the NeuroBlender zip file",
        # FIXME: remove hardcoded path
        default="/Users/michielk/workspace/NeuroBlender/NeuroBlender.zip")

    def execute(self, context):

        bpy.ops.wm.addon_install(filepath=self.path)
        bpy.ops.wm.addon_enable(module=self.name)

        return {"FINISHED"}


def engine_update(self, context):
    """Update materials when switching between engines."""

    scn = context.scene
    nb = scn.nb

    for mat in bpy.data.materials:
        mat.use_nodes = nb.engine == "CYCLES"
        if nb.engine.startswith("BLENDER"):
            nb_mat.CR2BR(mat)
        else:
            nb_mat.BR2CR(mat)

    scn.render.engine = nb.engine
    # TODO: handle lights


def engine_driver():

    scn = bpy.context.scene
    nb = scn.nb

    driver = nb.driver_add("engine", -1).driver
    driver.type = 'AVERAGE'

    nb_rp.create_var(driver, "type",
                     'SINGLE_PROP', 'SCENE',
                     scn, "render.engine")


def esp_path_update(self, context):
    """Add external site-packages path to sys.path."""

    nb_utils.add_path(self.esp_path)


def sformfile_update(self, context):
    """Set the sform transformation matrix for the object."""

    try:
        ob = bpy.data.objects[self.name]
    except:
        pass
    else:
        sformfile = bpy.path.abspath(self.sformfile)
        affine = nb_imp.read_affine_matrix(sformfile)
        ob.matrix_world = affine


def slices_update(self, context):
    """Set slicethicknesses and positions for the object."""

    ob = bpy.data.objects[self.name+"SliceBox"]
    ob.scale = self.slicethickness

    try:
        # FIXME: should this be scalargroups?
        scalar = self.scalars[self.index_scalars]
    except:
        matname = self.name
        mat = bpy.data.materials[matname]
        mat.type = mat.type
        mat.texture_slots[0].scale[0] = mat.texture_slots[0].scale[0]
    else:
        for scalar in self.scalars:
            mat = bpy.data.materials[scalar.matname]
            tss = [ts for ts in mat.texture_slots if ts is not None]
            for ts in tss:
                ts.scale[0] = ts.scale[0]

@persistent
def slices_handler(dummy):
    """Set surface or volume rendering for the voxelvolume."""

    scn = bpy.context.scene
    nb = scn.nb

    for vvol in nb.voxelvolumes:
        slices_update(vvol, bpy.context)
    for vvol in nb.voxelvolumes:
        for scalargroup in vvol.scalargroups:
            slices_update(scalargroup, bpy.context)
        for labelgroup in vvol.labelgroups:
            slices_update(labelgroup, bpy.context)

bpy.app.handlers.frame_change_pre.append(slices_handler)


def rendertype_enum_update(self, context):
    """Set surface or volume rendering for the voxelvolume."""

    try:
        matnames = [scalar.matname for scalar in self.scalars]
    except:
        matnames = [self.name]
    else:
        matnames = set(matnames)

    # FIXME: vvol.rendertype ideally needs to switch if mat.type does
    for matname in matnames:
        mat = bpy.data.materials[matname]
        mat.type = self.rendertype
        tss = [ts for ts in mat.texture_slots if ts is not None]
        for ts in tss:
            if mat.type == 'VOLUME':
                    for idx in range(0, 3):
                        ts.driver_remove("scale", idx)
                        ts.driver_remove("offset", idx)
                    ts.scale = [1, 1, 1]
                    ts.offset = [0, 0, 0]
            elif mat.type == 'SURFACE':
                for idx in range(0, 3):
                    nb_imp.voxelvolume_slice_drivers_surface(self, ts,
                                                              idx, "scale")
                    nb_imp.voxelvolume_slice_drivers_surface(self, ts,
                                                             idx, "offset")


# FIXME: excessive to remove/add these drivers at every frame;
# mostly just need an update of the offset values for texture mapping;
# except when keyframing rendertype!
@persistent
def rendertype_enum_handler(dummy):
    """Set surface or volume rendering for the voxelvolume."""

    scn = bpy.context.scene
    nb = scn.nb

    for vvol in nb.voxelvolumes:
        rendertype_enum_update(vvol, bpy.context)
    for vvol in nb.voxelvolumes:
        for scalargroup in vvol.scalargroups:
            rendertype_enum_update(scalargroup, bpy.context)
        for labelgroup in vvol.labelgroups:
            rendertype_enum_update(labelgroup, bpy.context)

bpy.app.handlers.frame_change_pre.append(rendertype_enum_handler)
# does this need to be post?


def is_yoked_bool_update(self, context):
    """Add or remove drivers linking voxelvolume and overlay."""

    nb_ob = nb_utils.active_nb_object()[0]
    for prop in ['slicethickness', 'sliceposition', 'sliceangle']:
        for idx in range(0, 3):
            if self.is_yoked:
                nb_imp.voxelvolume_slice_drivers_yoke(nb_ob, self, prop, idx)
            else:
                self.driver_remove(prop, idx)


def mat_is_yoked_bool_update(self, context):
    """Add or remove drivers linking overlay's materials."""

    pass
#     nb_ob = nb_utils.active_nb_object()[0]
#     for prop in ['slicethickness', 'sliceposition', 'sliceangle']:
#         for idx in range(0, 3):
#             if self.is_yoked:
#                 nb_imp.voxelvolume_slice_drivers_yoke(nb_ob, self, prop, idx)
#             else:
#                 self.driver_remove(prop, idx)


def mode_enum_update(self, context):
    """Perform actions for updating mode."""

    scn = context.scene
    nb = scn.nb

    for mat in bpy.data.materials:
        nb_mat.switch_mode_mat(mat, self.mode)

    try:
        nb_preset = nb.presets[self.index_presets]
        nb_cam = nb_preset.cameras[0]
        light_obs = [bpy.data.objects.get(light.name)
                     for light in nb_preset.lights]
        table_obs = [bpy.data.objects.get(table.name)
                     for table in nb_preset.tables]
    except:
        pass
    else:
        nb_rp.switch_mode_preset(light_obs, table_obs,
                                 nb.mode, nb_cam.cam_view)

    # TODO: switch colourbars


def overlay_enum_callback(self, context):
    """Populate the enum based on available options."""

    items = []
    items.append(("scalargroups", "scalars",
                  "List the scalar overlays", 0))
    if self.objecttype != 'tracts':
        items.append(("labelgroups", "labels",
                      "List the label overlays", 1))
    if self.objecttype == 'surfaces':
        items.append(("bordergroups", "borders",
                      "List the border overlays", 2))

    return items


def index_scalars_update(self, context):
    """Switch views on updating scalar index."""

    if hasattr(self, 'scalargroups'):  # TODO: isinstance
        try:
            sg = self.scalargroups[self.index_scalargroups]
        except IndexError:
            pass
        else:
            index_scalars_update_func(sg)
    else:
        sg = self
        index_scalars_update_func(sg)


@persistent
def index_scalars_handler_func(dummy):
    """"""

    scn = bpy.context.scene
    nb = scn.nb

    try:
        preset = nb.presets[nb.index_presets]
    except:
        pass
    else:
        for anim in preset.animations:
            if anim.animationtype == "TimeSeries":

                sgs = nb_rp.find_ts_scalargroups(anim)
                sg = sgs[anim.anim_timeseries]

                scalar = sg.scalars[sg.index_scalars]

                if sg.path_from_id().startswith("nb.surfaces"):
                    # update Image Sequence Texture index
                    mat = bpy.data.materials[sg.name]
                    itex = mat.node_tree.nodes["Image Texture"]
                    itex.image_user.frame_offset = scn.frame_current
                    # FIXME: more flexible indexing

                elif sg.path_from_id().startswith("nb.voxelvolumes"):
                    index_scalars_update_vvolscalar_func(sg, scalar,
                                                         nb.texmethod)


bpy.app.handlers.frame_change_pre.append(index_scalars_handler_func)


def index_scalars_update_func(group=None):
    """Switch views on updating overlay index."""

    scn = bpy.context.scene
    nb = scn.nb

    if group is None:
        group = nb_utils.active_nb_overlay()[0]

    nb_ob_path = '.'.join(group.path_from_id().split('.')[:-1])
    nb_ob = eval(nb_ob_path)
    ob = bpy.data.objects[nb_ob.name]

    try:
        scalar = group.scalars[group.index_scalars]
    except IndexError:
        pass
    else:
        name = scalar.name

        if group.path_from_id().startswith("nb.surfaces"):

            vg_idx = ob.vertex_groups.find(name)
            ob.vertex_groups.active_index = vg_idx

            if hasattr(group, 'scalars'):

                mat = bpy.data.materials[group.name]

                # update Image Sequence Texture index
                itex = mat.node_tree.nodes["Image Texture"]
                itex.image_user.frame_offset = group.index_scalars

                # update Vertex Color attribute
                attr = mat.node_tree.nodes["Attribute"]
                attr.attribute_name = name  # FIXME

                vc_idx = ob.data.vertex_colors.find(name)
                ob.data.vertex_colors.active_index = vc_idx

                for scalar in group.scalars:
                    scalar_index = group.scalars.find(scalar.name)
                    scalar.is_rendered = scalar_index == group.index_scalars

                # reorder materials: place active group on top
                mats = [mat for mat in ob.data.materials]
                mat_idx = ob.data.materials.find(group.name)
                mat = mats.pop(mat_idx)
                mats.insert(0, mat)
                ob.data.materials.clear()
                for mat in mats:
                    ob.data.materials.append(mat)

        if group.path_from_id().startswith("nb.tracts"):
            if hasattr(group, 'scalars'):
                for i, spline in enumerate(ob.data.splines):
                    splname = name + '_spl' + str(i).zfill(8)
                    spline.material_index = ob.material_slots.find(splname)

        # FIXME: used texture slots
        if group.path_from_id().startswith("nb.voxelvolumes"):
            if hasattr(group, 'scalars'):

                index_scalars_update_vvolscalar_func(group, scalar,
                                                     nb.texmethod)


def index_scalars_update_vvolscalar_func(group, scalar, method=1):
    """Switch views on updating overlay index."""

    if method == 1:  # simple filepath switching

        try:
            img = bpy.data.images[group.name]
        except KeyError:
            pass
        else:
            # this reloads the sequence/updates the viewport
            try:
                tex = bpy.data.textures[group.name]
            except KeyError:
                pass
            else:
                img.filepath = scalar.filepath
                tex.voxel_data.file_format = group.texformat

    elif method == 2:

        props = ("density_factor", "emission_factor", "emission_color_factor",
                 "emit_factor", "diffuse_color_factor", "alpha_factor")

        for sc in group.scalars:
            mat = bpy.data.materials[sc.matname]
            ts = mat.texture_slots[sc.tex_idx]
            ts.use = True
            for prop in props:
                exec('ts.%s = 0' % prop)

        mat = bpy.data.materials[scalar.matname]
        ts = mat.texture_slots[scalar.tex_idx]
        print(mat, ts, scalar.tex_idx)
        for prop in props:
            exec('ts.%s = 1' % prop)

    elif method == 3:
        mat = bpy.data.materials[group.name]
        tss = [(i, ts) for i, ts in enumerate(mat.texture_slots)
               if ts is not None]
        props = ("density_factor", "emission_factor", "emission_color_factor",
                 "emit_factor", "diffuse_color_factor", "alpha_factor")
        for i, ts in tss:
            ts.use = group.index_scalars == i
            v = 1
            for prop in props:
                exec('ts.%s = v' % prop)

    elif method == 4:  # simple texture switching in slot 0
        try:
            mat = bpy.data.materials[scalar.matname]
            tex = bpy.data.textures[scalar.texname]
        except:
            pass
        else:
            mat.texture_slots[0].texture = tex


def index_labels_update(self, context):
    """Switch views on updating label index."""

    if hasattr(self, 'labelgroups'):  # TODO: isinstance
        try:
            lg = self.labelgroups[self.index_labelgroups]
        except IndexError:
            pass
        else:
            index_labels_update_func(lg)
    else:
        lg = self
        index_labels_update_func(lg)


def index_labels_update_func(group=None):
    """Switch views on updating overlay index."""

    scn = bpy.context.scene
    nb = scn.nb

    nb_ob_path = '.'.join(group.path_from_id().split('.')[:-1])
    nb_ob = eval(nb_ob_path)
    ob = bpy.data.objects[nb_ob.name]

    if group is None:
        group = nb_utils.active_nb_overlay()[0]

    try:
        label = group.labels[group.index_labels]
    except IndexError:
        pass
    else:
        name = label.name

        if "surfaces" in group.path_from_id():
            vg_idx = ob.vertex_groups.find(name)
            ob.vertex_groups.active_index = vg_idx


def material_update(self, context):
    """Assign a new preset material to the object."""

    mat = bpy.data.materials[self.name]
    if context.scene.nb.engine.startswith("BLENDER"):
        nb_mat.CR2BR(mat)


def material_enum_update(self, context):
    """Assign a new preset material to the object."""

    mat = bpy.data.materials[self.name]
    nb_mat.link_innode(mat, self.colourtype)


def colourmap_enum_update(self, context):
    """Assign a new colourmap to the object."""

    nb_ob = nb_utils.active_nb_object()[0]
    if hasattr(nb_ob, 'slicebox'):
        cr = bpy.data.textures[self.name].color_ramp
    else:
        if hasattr(nb_ob, "nstreamlines"):
            ng = bpy.data.node_groups.get("TractOvGroup")
            cr = ng.nodes["ColorRamp"].color_ramp
        elif hasattr(nb_ob, "sphere"):
            nt = bpy.data.materials[self.name].node_tree
            cr = nt.nodes["ColorRamp"].color_ramp

    colourmap = self.colourmap_enum
    nb_mat.switch_colourmap(cr, colourmap)


def cam_view_enum_XX_update(self, context):
    """Set the camview property from enum options."""

    scn = context.scene
    nb = scn.nb
    nb_preset = nb.presets[nb.index_presets]

    lud = {'Centre': 0,
           'Left': -1, 'Right': 1,
           'Anterior': 1, 'Posterior': -1,
           'Superior': 1, 'Inferior': -1}

    LR = lud[self.cam_view_enum_LR]
    AP = lud[self.cam_view_enum_AP]
    IS = lud[self.cam_view_enum_IS]

    cv_unit = mathutils.Vector([LR, AP, IS]).normalized()

    self.cam_view = list(cv_unit * self.cam_distance)

    cam = bpy.data.objects[self.name]
    centre = bpy.data.objects[nb_preset.centre]

#     nb_rp.cam_view_update(cam, centre, self.cam_view, nb_preset.dims)
    cam.location = self.cam_view

    scn.frame_set(0)


def presets_enum_callback(self, context):
    """Populate the enum based on available options."""

    items = [(ps.name, ps.name, "List the presets", i)
             for i, ps in enumerate(self.presets)]

    return items


def presets_enum_update(self, context):
    """Update the preset enum."""

    scn = context.scene
    nb = scn.nb

    self.index_presets = self.presets.find(self.presets_enum)
    preset = self.presets[self.index_presets]
    scn.camera = bpy.data.objects[preset.cameras[0].name]
    # TODO:
    # switch cam view etc


def campaths_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    items = [(cp.name, cp.name, "List the camera paths", i)
             for i, cp in enumerate(nb.campaths)]

    return items


def campaths_enum_update(self, context):
    """Update the camera path."""

    scn = context.scene
    nb = scn.nb
    nb_preset = nb.presets[nb.index_presets]
    cam = bpy.data.objects[nb_preset.cameras[0].name]
    anim = nb_preset.animations[nb_preset.index_animations]

    if anim.animationtype == "CameraPath": # FIXME: overkill?
        cam_anims = [anim for anim in nb_preset.animations
                     if ((anim.animationtype == "CameraPath") &
                         (anim.is_rendered))]
        nb_rp.clear_camera_path_animations(cam, nb_preset.animations,
                                           [nb_preset.index_animations])
        nb_rp.create_camera_path_animations(cam, cam_anims)


def tracktype_enum_update(self, context):
    """Update the camera path constraints."""

    scn = context.scene
    nb = scn.nb
    nb_preset = nb.presets[nb.index_presets]
    cam = bpy.data.objects[nb_preset.cameras[0].name]
    centre = bpy.data.objects[nb_preset.centre]
    anim = nb_preset.animations[nb_preset.index_animations]

    cam_anims = [anim for anim in nb_preset.animations
                 if ((anim.animationtype == "CameraPath") &
                     (anim.is_rendered))]

    anim_blocks = [[anim.anim_block[0], anim.anim_block[1]]
                   for anim in cam_anims]

    timeline = nb_rp.generate_timeline(scn, cam_anims, anim_blocks)
    cnsTT = cam.constraints["TrackToCentre"]
    nb_rp.restrict_incluence_timeline(scn, cnsTT, timeline, group="TrackTo")

    # TODO: if not yet executed/exists
    cns = cam.constraints["FollowPath" + anim.campaths_enum]
    cns.use_curve_follow = anim.tracktype == "TrackPath"
    if anim.tracktype == 'TrackPath':
        cns.forward_axis = 'TRACK_NEGATIVE_Z'
        cns.up_axis = 'UP_Y'
    else:
        cns.forward_axis = 'TRACK_NEGATIVE_Y'
        cns.up_axis = 'UP_Z'


def direction_toggle_update(self, context):
    """Update the direction of animation on a curve."""

    scn = context.scene
    nb = scn.nb
    nb_preset = nb.presets[nb.index_presets]
    anim = nb_preset.animations[nb_preset.index_animations]

    try:
        campath = bpy.data.objects[anim.campaths_enum]
    except:
        pass
    else:
        animdata = campath.data.animation_data
        fcu = animdata.action.fcurves.find("eval_time")
        mod = fcu.modifiers[0]  # TODO: sloppy
        intercept, slope, _ = nb_rp.calculate_coefficients(campath, anim)
        mod.coefficients = (intercept, slope)


def tracts_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    items = [(tract.name, tract.name, "List the tracts", i)
             for i, tract in enumerate(nb.tracts)]

    return items


def surfaces_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    items = [(surface.name, surface.name, "List the surfaces", i)
             for i, surface in enumerate(nb.surfaces)]

    return items


def timeseries_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    # FIXME: crash when commenting/uncommenting this
    aliases = {'T': 'tracts', 'S': 'surfaces', 'V': 'voxelvolumes'}
    try:
        coll = eval('nb.%s' % aliases[self.timeseries_object[0]])
        sgs = coll[self.timeseries_object[3:]].scalargroups
    except:
        items = []
    else:
#     sgs = nb_rp.find_ts_scalargroups(self)
        items = [(scalargroup.name, scalargroup.name, "List the timeseries", i)
                 for i, scalargroup in enumerate(sgs)]

    return items


def voxelvolumes_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    items = [(vvol.name, vvol.name, "List the voxelvolumes", i)
             for i, vvol in enumerate(nb.voxelvolumes)]

    return items


def curves_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    campaths = [cp.name for cp in nb.campaths]
    tracts = [tract.name for tract in nb.tracts]
    items = [(cu.name, cu.name, "List the curves", i)
             for i, cu in enumerate(bpy.data.curves)
             if ((cu.name not in campaths) and
                 (cu.name not in tracts))]

    return items


def timeseries_object_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    nb_obs = ["%s: %s" % (l, ob.name)
              for l, coll in zip(['T', 'S', 'V'], [nb.tracts,
                                                   nb.surfaces,
                                                   nb.voxelvolumes])
              for ob in coll if len(ob.scalargroups)]
    items = [(obname, obname, "List the objects", i)
             for i, obname in enumerate(nb_obs)]

    return items


def texture_directory_update(self, context):
    """Update the texture."""

    if "surfaces" in self.path_from_id():
        nb_mat.load_surface_textures(self.name, self.texdir, len(self.scalars))
    elif "voxelvolumes" in self.path_from_id():
        pass  # TODO


def trackobject_enum_callback(self, context):
    """Populate the enum based on available options."""

    items = [(ob.name, ob.name, "List all objects", i+1)
             for i, ob in enumerate(bpy.data.objects)]
    items.insert(0, ("None", "None", "None", 0))

    return items


def trackobject_enum_update(self, context):
    """Update the camera."""

    # TODO: evaluate against animations
    scn = context.scene
    nb = scn.nb

    preset = nb.presets[nb.index_presets]
    cam = bpy.data.objects[self.name]
    cns = cam.constraints["TrackToCentre"]
    if self.trackobject == "None":
        cns.mute = True
    else:
        try:
            cns.mute = False
            cns.target = bpy.data.objects[self.trackobject]
        except KeyError:
            infostring = "Object {} not found: disabling tracking"
            print(infostring.format(self.trackobject))


def update_viewport():
    """Trigger viewport updates"""

    for area in bpy.context.screen.areas:
        if area.type in ['IMAGE_EDITOR', 'VIEW_3D', 'PROPERTIES']:
            area.tag_redraw()


def light_update(self, context):
    """Update light."""

    scn = context.scene
    nb = scn.nb

    light_ob = bpy.data.objects[self.name]

    light_ob.hide = not self.is_rendered
    light_ob.hide_render = not self.is_rendered

    light = bpy.data.lamps[self.name]

    light.type = self.type

    if scn.render.engine == "CYCLES":
        light.use_nodes = True
        node = light.node_tree.nodes["Emission"]
        node.inputs[1].default_value = self.strength
    elif scn.render.engine == "BLENDER_RENDER":
        light.energy = self.strength


def table_update(self, context):
    """Update table."""

    scn = context.scene
    nb = scn.nb

    table = bpy.data.objects[self.name]

    table.hide = not self.is_rendered
    table.hide_render = not self.is_rendered


def update_name(self, context):
    """Update the name of a NeuroBlender collection item."""

    scn = context.scene
    nb = scn.nb

    def rename_voxelvolume(vvol):
        colls = [bpy.data.objects,
                 bpy.data.meshes,
                 bpy.data.materials,
                 bpy.data.textures,
                 bpy.data.images]
        bpy.data.objects[vvol.name_mem+"SliceBox"].name = vvol.name+"SliceBox"
        return colls

    def rename_group(coll, group):
        for item in group:
            if item.name.startswith(coll.name_mem):
                item_split = item.name.split('.')
                # FIXME: there can be multiple dots in name
                if len(item_split) > 1:
                    newname = '.'.join([coll.name, item_split[-1]])
                else:
                    newname = coll.name
                item.name = newname

    dp_split = re.findall(r"[\w']+", self.path_from_id())
    colltype = dp_split[-2]

    if colltype == "tracts":
        colls = [bpy.data.objects,
                 bpy.data.curves,
                 bpy.data.materials]

    elif colltype == "surfaces":
        # NOTE/TODO: ref to sphere
        colls = [bpy.data.objects,
                 bpy.data.meshes,
                 bpy.data.materials]

    elif colltype == "voxelvolumes":
        colls = rename_voxelvolume(self)

    elif colltype == "scalargroups":
        parent = '.'.join(self.path_from_id().split('.')[:-1])
        parent_coll = eval(parent)
        parent_ob = bpy.data.objects[parent_coll.name]
        if parent.startswith("nb.tracts"):
            # FIXME: make sure collection name and matnames agree!
            rename_group(self, bpy.data.materials)
            colls = []
        elif parent.startswith("nb.surfaces"):
            rename_group(self, parent_ob.vertex_groups)
            colls = [bpy.data.materials]
        elif parent.startswith("nb.voxelvolumes"):
            colls = rename_voxelvolume(self)
        rename_group(self, self.scalars)

    elif colltype == "labelgroups":
        parent = '.'.join(self.path_from_id().split('.')[:-1])
        if parent.startswith("nb.tracts"):
            colls = []  # N/A
        elif parent.startswith("nb.surfaces"):
            colls = [bpy.data.materials]
        elif parent.startswith("nb.voxelvolumes"):
            colls = rename_voxelvolume(self)

    elif colltype == "bordergroups":
        colls = [bpy.data.objects]

    elif colltype == "scalars":
        colls = []  # irrelevant: name not referenced

    elif colltype == "labels":
        parent = '.'.join(self.path_from_id().split('.')[:-2])
        parent_coll = eval(parent)
        parent_ob = bpy.data.objects[parent_coll.name]
        if parent.startswith("nb.tracts"):
            colls = []  # N/A
        elif parent.startswith("nb.surfaces"):
            vg = parent_ob.vertex_groups.get(self.name_mem)
            vg.name = self.name
            colls = [bpy.data.materials]
        elif parent.startswith("nb.voxelvolumes"):
            colls = []  # irrelevant: name not referenced

    elif colltype == "borders":
        colls = [bpy.data.objects,
                 bpy.data.curves,
                 bpy.data.materials]

    elif colltype == "presets":
        colls = [bpy.data.objects]

    elif colltype == "cameras":  # not implemented via Panels
        colls = [bpy.data.objects,
                 bpy.data.cameras]  # animations?

    elif colltype == "lights":
        colls = [bpy.data.objects,
                 bpy.data.lamps]

    elif colltype == "tables":  # not implemented via Panels
        colls = [bpy.data.objects,
                 bpy.data.meshes,
                 bpy.data.materials]

    elif colltype == "lights":
        colls = [bpy.data.objects,
                 bpy.data.lamps]

    elif colltype == "campaths":  # not implemented via Panels
        colls = [bpy.data.objects,
                 bpy.data.curves]  # FollowPath constraints

    else:
        colls = []

    for coll in colls:
        coll[self.name_mem].name = self.name

    self.name_mem = self.name


class ColorRampProperties(PropertyGroup):
    """Custom properties of color ramps."""

    name = StringProperty(
        name="Name",
        description="The name of the color stop",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    nn_position = FloatProperty(
        name="nn_position",
        description="The non-normalized position of the color stop",
        default=0,
        precision=4)


class ScalarProperties(PropertyGroup):
    """Properties of scalar overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the scalar overlay",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the scalar overlay",
        subtype="FILE_PATH")
    icon = StringProperty(
        name="Icon",
        description="Icon for scalar overlays",
        default="FORCE_CHARGE")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the overlay is rendered",
        default=True)
    parent = StringProperty(
        name="Parent",
        description="The name of the parent object")
    range = FloatVectorProperty(
        name="Range",
        description="The original min-max of scalars mapped in vertexweights",
        default=(0, 0),
        size=2,
        precision=4)
    colourmap_enum = EnumProperty(
        name="colourmap",
        description="Apply this colour map",
        items=[("greyscale", "greyscale", "greyscale", 1),
               ("jet", "jet", "jet", 2),
               ("hsv", "hsv", "hsv", 3),
               ("hot", "hot", "hot", 4),
               ("cool", "cool", "cool", 5),
               ("spring", "spring", "spring", 6),
               ("summer", "summer", "summer", 7),
               ("autumn", "autumn", "autumn", 8),
               ("winter", "winter", "winter", 9),
               ("parula", "parula", "parula", 10)],
        default="jet",
        update=colourmap_enum_update)
    nn_elements = CollectionProperty(
        type=ColorRampProperties,
        name="nn_elements",
        description="The non-normalized color stops")
    index_nn_elements = IntProperty(
        name="nn_element index",
        description="Index of the non-normalized color stops",
        default=0,
        min=0)
    showcolourbar = BoolProperty(
        name="Render colourbar",
        description="Show/hide colourbar in rendered image",
        default=False)
    colourbar_placement = EnumProperty(
        name="Colourbar placement",
        description="Choose where to show the colourbar",
        default="top-right",
        items=[("top-right", "top-right",
                "Place colourbar top-right"),
               ("top-left", "top-left",
                "Place colourbar top-left"),
               ("bottom-right", "bottom-right",
                "Place colourbar bottom-right"),
               ("bottom-left", "bottom-left",
                "Place colourbar bottom-left")])  # update=colourbar_update
    colourbar_size = FloatVectorProperty(
        name="size",
        description="Set the size of the colourbar",
        default=[0.25, 0.05],
        size=2, min=0., max=1.)
    colourbar_position = FloatVectorProperty(
        name="position",
        description="Set the position of the colourbar",
        default=[1., 1.],
        size=2, min=-1., max=1.)
    textlabel_colour = FloatVectorProperty(
        name="Textlabel colour",
        description="Pick a colour",
        default=[1.0, 1.0, 1.0],
        subtype="COLOR")
    textlabel_placement = EnumProperty(
        name="Textlabel placement",
        description="Choose where to show the label",
        default="out",
        items=[("out", "out", "Place labels outside"),
               ("in", "in", "Place labels inside")])  # update=textlabel_update
    textlabel_size = FloatProperty(
        name="Textlabel size",
        description="Set the size of the textlabel (relative to colourbar)",
        default=0.5,
        min=0.,
        max=1.)

    matname = StringProperty(
        name="Material name",
        description="The name of the scalar overlay")
    texname = StringProperty(
        name="Texture name",
        description="The name of the scalar overlay")
    tex_idx = IntProperty(
        name="Texture index",
        description="The name of the scalar overlay")


class LabelProperties(PropertyGroup):
    """Properties of label overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the label overlay",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for label overlays",
        default="BRUSH_VERTEXDRAW")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the label is rendered",
        default=True)
    parent = StringProperty(
        name="Parent",
        description="The name of the parent object")
    group = StringProperty(
        name="Group",
        description="The group the border overlay belongs to")
    value = IntProperty(
        name="Label value",
        description="The value of the label in vertexgroup 'scalarname'",
        default=0)
    colour = FloatVectorProperty(
        name="Label color",
        description="The color of the label in vertexgroup 'scalarname'",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        update=material_update)


class BorderProperties(PropertyGroup):
    """Properties of border overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the border overlay",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for border overlays",
        default="CURVE_BEZCIRCLE")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the border is rendered",
        default=True)
    parent = StringProperty(
        name="Parent",
        description="The name of the parent object")
    group = StringProperty(
        name="Group",
        description="The group the border overlay belongs to")
    value = IntProperty(
        name="Label value",
        description="The value of the label in vertexgroup 'scalarname'",
        default=0)
    colour = FloatVectorProperty(
        name="Border color",
        description="The color of the border",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        update=material_update)


class ScalarGroupProperties(PropertyGroup):
    """Properties of time series overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the time series overlay",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the time series overlay",
        subtype="FILE_PATH")
    icon = StringProperty(
        name="Icon",
        description="Icon for time series overlays",
        default="TIME")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the overlay is rendered",
        default=True)
    parent = StringProperty(
        name="Parent",
        description="The name of the parent object")

    scalars = CollectionProperty(
        type=ScalarProperties,
        name="scalars",
        description="The collection of loaded scalars")
    index_scalars = IntProperty(
        name="scalar index",
        description="index of the scalars collection",
        default=0,
        min=0,
        update=index_scalars_update)

    range = FloatVectorProperty(
        name="Range",
        description="The original min-max of scalars mapped in vertexweights",
        default=(0, 0),
        size=2,
        precision=4)
    colourmap_enum = EnumProperty(
        name="colourmap",
        description="Apply this colour map",
        items=[("greyscale", "greyscale", "greyscale", 1),
               ("jet", "jet", "jet", 2),
               ("hsv", "hsv", "hsv", 3),
               ("hot", "hot", "hot", 4),
               ("cool", "cool", "cool", 5),
               ("spring", "spring", "spring", 6),
               ("summer", "summer", "summer", 7),
               ("autumn", "autumn", "autumn", 8),
               ("winter", "winter", "winter", 9),
               ("parula", "parula", "parula", 10)],
        default="jet",
        update=colourmap_enum_update)
    nn_elements = CollectionProperty(
        type=ColorRampProperties,
        name="nn_elements",
        description="The non-normalized color stops")
    index_nn_elements = IntProperty(
        name="nn_element index",
        description="Index of the non-normalized color stops",
        default=0,
        min=0)
    showcolourbar = BoolProperty(
        name="Render colourbar",
        description="Show/hide colourbar in rendered image",
        default=False)
    colourbar_placement = EnumProperty(
        name="Colourbar placement",
        description="Choose where to show the colourbar",
        default="top-right",
        items=[("top-right", "top-right",
                "Place colourbar top-right"),
               ("top-left", "top-left",
                "Place colourbar top-left"),
               ("bottom-right", "bottom-right",
                "Place colourbar bottom-right"),
               ("bottom-left", "bottom-left",
                "Place colourbar bottom-left")])  # update=colourbar_update
    colourbar_size = FloatVectorProperty(
        name="size",
        description="Set the size of the colourbar",
        default=[0.25, 0.05],
        size=2, min=0., max=1.)
    colourbar_position = FloatVectorProperty(
        name="position",
        description="Set the position of the colourbar",
        default=[1., 1.],
        size=2, min=-1., max=1.)
    textlabel_colour = FloatVectorProperty(
        name="Textlabel colour",
        description="Pick a colour",
        default=[1.0, 1.0, 1.0],
        subtype="COLOR")
    textlabel_placement = EnumProperty(
        name="Textlabel placement",
        description="Choose where to show the label",
        default="out",
        items=[("out", "out", "Place labels outside"),
               ("in", "in", "Place labels inside")])  # update=textlabel_update
    textlabel_size = FloatProperty(
        name="Textlabel size",
        description="Set the size of the textlabel (relative to colourbar)",
        default=0.5,
        min=0.,
        max=1.)

    rendertype = EnumProperty(
        name="rendertype",
        description="Surface or volume rendering of texture",
        items=[("SURFACE", "Surface",
                "Switch to surface rendering", 0),
               ("VOLUME", "Volume",
                "Switch to volume rendering", 2)],
        update=rendertype_enum_update,
        default="VOLUME")

    slicebox = StringProperty(
        name="Slicebox",
        description="Name of slicebox",
        default="box")
    slicethickness = FloatVectorProperty(
        name="Slice thickness",
        description="The thickness of the slices",
        default=(1.0, 1.0, 1.0),
        size=3,
        precision=4,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceposition = FloatVectorProperty(
        name="Slice position",
        description="The position of the slices",
        default=(0.5, 0.5, 0.5),
        size=3,
        precision=4,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceangle = FloatVectorProperty(
        name="Slice position",
        description="The position of the slices",
        default=(0.0, 0.0, 0.0),
        size=3,
        precision=4,
        min=-1.5708,
        max=1.5708,
        subtype="TRANSLATION",
        update=slices_update)
    is_yoked = BoolProperty(
        name="Is Yoked",
        description="Indicates if the overlay is yoked to parent",
        default=False,
        update=is_yoked_bool_update)
    dimensions = FloatVectorProperty(
        name="dimensions",
        description="",
        default=[0.0, 0.0, 0.0, 0.0],
        size=4,
        subtype="TRANSLATION")

    texdir = StringProperty(
        name="Texture directory",
        description="The directory with textures",
        subtype="DIR_PATH",
        update=texture_directory_update)
    texformat = EnumProperty(
        name="Volume texture file format",
        description="Choose a format to save volume textures",
        default="IMAGE_SEQUENCE",
        items=[("IMAGE_SEQUENCE", "IMAGE_SEQUENCE", "IMAGE_SEQUENCE", 0),
               ("STRIP", "STRIP", "STRIP", 1),
               ("RAW_8BIT", "RAW_8BIT", "RAW_8BIT", 2)])

    mat_is_yoked = BoolProperty(
        name="Material Is Yoked",
        description="Indicates if the overlay time point materials are yoked",
        default=True,
        update=mat_is_yoked_bool_update)


class LabelGroupProperties(PropertyGroup):
    """Properties of label groups."""

    name = StringProperty(
        name="Name",
        description="The name of the label overlay",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the label overlay",
        subtype="FILE_PATH")
    icon = StringProperty(
        name="Icon",
        description="Icon for label overlays",
        default="BRUSH_VERTEXDRAW")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the label is rendered",
        default=True)
    parent = StringProperty(
        name="Parent",
        description="The name of the parent object")

    labels = CollectionProperty(
        type=LabelProperties,
        name="labels",
        description="The collection of loaded labels")
    index_labels = IntProperty(
        name="label index",
        description="index of the labels collection",
        default=0,
        min=0,
        update=index_labels_update)

    range = FloatVectorProperty(
        name="Range",
        description="The original min-max of scalars mapped in vertexweights",
        default=(0, 0),
        size=2,
        precision=4)
    colourmap_enum = EnumProperty(
        name="colourmap",
        description="Apply this colour map",
        items=[("greyscale", "greyscale", "greyscale", 1),
               ("jet", "jet", "jet", 2),
               ("hsv", "hsv", "hsv", 3),
               ("hot", "hot", "hot", 4),
               ("cool", "cool", "cool", 5),
               ("spring", "spring", "spring", 6),
               ("summer", "summer", "summer", 7),
               ("autumn", "autumn", "autumn", 8),
               ("winter", "winter", "winter", 9),
               ("parula", "parula", "parula", 10)],
        default="jet",
        update=colourmap_enum_update)
    nn_elements = CollectionProperty(
        type=ColorRampProperties,
        name="nn_elements",
        description="The non-normalized color stops")
    index_nn_elements = IntProperty(
        name="nn_element index",
        description="Index of the non-normalized color stops",
        default=0,
        min=0)

    rendertype = EnumProperty(
        name="rendertype",
        description="Surface or volume rendering of texture",
        items=[("SURFACE", "Surface",
                "Switch to surface rendering", 0),
               ("VOLUME", "Volume",
                "Switch to volume rendering", 2)],
        update=rendertype_enum_update,
        default="VOLUME")

    slicebox = StringProperty(
        name="Slicebox",
        description="Name of slicebox",
        default="box")
    slicethickness = FloatVectorProperty(
        name="Slice thickness",
        description="The thickness of the slices",
        default=(1.0, 1.0, 1.0),
        size=3,
        precision=4,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceposition = FloatVectorProperty(
        name="Slice position",
        description="The position of the slices",
        default=(0.5, 0.5, 0.5),
        size=3,
        precision=4,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceangle = FloatVectorProperty(
        name="Slice position",
        description="The position of the slices",
        default=(0.0, 0.0, 0.0),
        size=3,
        precision=4,
        min=-1.5708,
        max=1.5708,
        subtype="TRANSLATION",
        update=slices_update)
    is_yoked = BoolProperty(
        name="Is Yoked",
        description="Indicates if the overlay is yoked to parent",
        default=False,
        update=is_yoked_bool_update)
    dimensions = FloatVectorProperty(
        name="dimensions",
        description="",
        default=[0.0, 0.0, 0.0, 0.0],
        size=4,
        subtype="TRANSLATION")

    texdir = StringProperty(
        name="Texture directory",
        description="The directory with textures",
        subtype="DIR_PATH",
        update=texture_directory_update)
    texformat = EnumProperty(
        name="Volume texture file format",
        description="Choose a format to save volume textures",
        default="IMAGE_SEQUENCE",
        items=[("IMAGE_SEQUENCE", "IMAGE_SEQUENCE", "IMAGE_SEQUENCE", 0),
               ("STRIP", "STRIP", "STRIP", 1),
               ("RAW_8BIT", "RAW_8BIT", "RAW_8BIT", 2)])


class BorderGroupProperties(PropertyGroup):
    """Properties of border groups."""

    name = StringProperty(
        name="Name",
        description="The name of the border overlay",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the border overlay",
        subtype="FILE_PATH")
    icon = StringProperty(
        name="Icon",
        description="Icon for border overlays",
        default="CURVE_BEZCIRCLE")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the border is rendered",
        default=True)
    parent = StringProperty(
        name="Parent",
        description="The name of the parent object")

    borders = CollectionProperty(
        type=BorderProperties,
        name="borders",
        description="The collection of loaded borders")
    index_borders = IntProperty(
        name="border index",
        description="index of the borders collection",
        default=0,
        min=0)

    texdir = StringProperty(
        name="Texture directory",
        description="The directory with textures",
        subtype="DIR_PATH",
        update=texture_directory_update)
    texformat = EnumProperty(
        name="Volume texture file format",
        description="Choose a format to save volume textures",
        default="IMAGE_SEQUENCE",
        items=[("IMAGE_SEQUENCE", "IMAGE_SEQUENCE", "IMAGE_SEQUENCE", 0),
               ("STRIP", "STRIP", "STRIP", 1),
               ("RAW_8BIT", "RAW_8BIT", "RAW_8BIT", 2)])


class TractProperties(PropertyGroup):
    """Properties of tracts."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the tract (default: filename)",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the tract",
        subtype="FILE_PATH")
    icon = StringProperty(
        name="Icon",
        description="Icon for tract objects",
        default="CURVE_BEZCURVE")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the overlay is rendered",
        default=True)
    beautified = BoolProperty(
        name="Beautify",
        description="Apply initial bevel on streamlines",
        default=True)

    sformfile = StringProperty(
        name="Transform",
        description="""
            A file with transformation matrix
            It can be a nifti file (through nibabel)
            or an ascii with a space-delimited 4x4 matrix
            For .nii, it will only use the sform for now
            """,
        subtype="FILE_PATH",
        update=sformfile_update)
    srow_x = FloatVectorProperty(
        name="srow_x",
        description="",
        default=[1.0, 0.0, 0.0, 0.0],
        size=4)
    srow_y = FloatVectorProperty(
        name="srow_y",
        description="",
        default=[0.0, 1.0, 0.0, 0.0],
        size=4)
    srow_z = FloatVectorProperty(
        name="srow_z",
        description="",
        default=[0.0, 0.0, 1.0, 0.0],
        size=4)

    scalargroups = CollectionProperty(
        type=ScalarGroupProperties,
        name="scalargroups",
        description="The collection of loaded scalargroups")
    index_scalargroups = IntProperty(
        name="scalargroup index",
        description="index of the scalargroups collection",
        default=0,
        min=0)
    labelgroups = CollectionProperty(
        type=LabelGroupProperties,
        name="labelgroups",
        description="The collection of loaded labelgroups")
    index_labelgroups = IntProperty(
        name="labelgroup index",
        description="index of the labelgroups collection",
        default=0,
        min=0)

    colourtype = EnumProperty(
        name="colourtype",
        description="Apply this colour method",
        items=[("basic", "basic",
                "Switch to basic material", 1),
               ("directional", "directional",
                "Switch to directional colour-coding", 2)],
        update=material_enum_update)
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR",
        update=material_update)
    transparency = FloatProperty(
        name="Transparency",
        description="Set the transparency",
        default=1.,
        min=0.,
        max=1.,
        update=material_update)

    nstreamlines = IntProperty(
        name="Nstreamlines",
        description="Number of streamlines in the tract (before weeding)",
        min=0)
    streamlines_interpolated = FloatProperty(
        name="Interpolate streamlines",
        description="Interpolate the individual streamlines",
        default=1.,
        min=0.,
        max=1.)
    tract_weeded = FloatProperty(
        name="Tract weeding",
        description="Retain a random selection of streamlines",
        default=1.,
        min=0.,
        max=1.)


class SurfaceProperties(PropertyGroup):
    """Properties of surfaces."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the surface (default: filename)",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the surface",
        subtype="FILE_PATH")
    icon = StringProperty(
        name="Icon",
        description="Icon for surface objects",
        default="MESH_MONKEY")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the overlay is rendered",
        default=True)
    beautified = BoolProperty(
        name="Beautify",
        description="Apply initial smoothing on surface",
        default=True)

    sformfile = StringProperty(
        name="Transform",
        description="""
            A file with transformation matrix
            It can be a nifti file (through nibabel)
            or an ascii with a space-delimited 4x4 matrix
            For .nii, it will only use the sform for now
            """,
        subtype="FILE_PATH",
        update=sformfile_update)
    srow_x = FloatVectorProperty(
        name="srow_x",
        description="",
        default=[1.0, 0.0, 0.0, 0.0],
        size=4)
    srow_y = FloatVectorProperty(
        name="srow_y",
        description="",
        default=[0.0, 1.0, 0.0, 0.0],
        size=4)
    srow_z = FloatVectorProperty(
        name="srow_z",
        description="",
        default=[0.0, 0.0, 1.0, 0.0],
        size=4)

    scalargroups = CollectionProperty(
        type=ScalarGroupProperties,
        name="scalargroups",
        description="The collection of loaded timeseries")
    index_scalargroups = IntProperty(
        name="scalargroup index",
        description="index of the scalargroups collection",
        default=0,
        min=0,
        update=index_scalars_update)
    labelgroups = CollectionProperty(
        type=LabelGroupProperties,
        name="labelgroups",
        description="The collection of loaded labelgroups")
    index_labelgroups = IntProperty(
        name="labelgroup index",
        description="index of the labelgroups collection",
        default=0,
        min=0,
        update=index_labels_update)
    bordergroups = CollectionProperty(
        type=BorderGroupProperties,
        name="bordergroups",
        description="The collection of loaded bordergroups")
    index_bordergroups = IntProperty(
        name="bordergroup index",
        description="index of the bordergroups collection",
        default=0,
        min=0)

    colourtype = EnumProperty(
        name="colourtype",
        description="Apply this colour method",
        items=[("basic", "basic",
                "Switch to basic material", 1),
               ("directional", "directional",
                "Switch to directional colour-coding", 2)],
        update=material_enum_update)
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR",
        update=material_update)
    transparency = FloatProperty(
        name="Transparency",
        description="Set the transparency",
        default=1.0,
        update=material_update)

    sphere = EnumProperty(
        name="Unwrapping sphere",
        description="Select sphere for unwrapping",
        items=surfaces_enum_callback)


class VoxelvolumeProperties(PropertyGroup):
    """Properties of voxelvolumes."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the voxelvolume (default: filename)",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    filepath = StringProperty(
        name="Filepath",
        description="The filepath to the voxelvolume",
        subtype="FILE_PATH")
    icon = StringProperty(
        name="Icon",
        description="Icon for surface objects",
        default="MESH_GRID")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the overlay is rendered",
        default=True)
    beautified = BoolProperty(
        name="Beautify",
        description="",
        default=True)

    sformfile = StringProperty(
        name="Transform",
        description="""
            A file with transformation matrix
            It can be a nifti file (through nibabel)
            or an ascii with a space-delimited 4x4 matrix
            For .nii, it will only use the sform for now
            """,
        subtype="FILE_PATH",
        update=sformfile_update)
    srow_x = FloatVectorProperty(
        name="srow_x",
        description="",
        default=[1.0, 0.0, 0.0, 0.0],
        size=4)
    srow_y = FloatVectorProperty(
        name="srow_y",
        description="",
        default=[0.0, 1.0, 0.0, 0.0],
        size=4)
    srow_z = FloatVectorProperty(
        name="srow_z",
        description="",
        default=[0.0, 0.0, 1.0, 0.0],
        size=4)
    dimensions = FloatVectorProperty(
        name="dimensions",
        description="",
        default=[0.0, 0.0, 0.0, 0.0],
        size=4,
        subtype="TRANSLATION")

    scalargroups = CollectionProperty(
        type=ScalarGroupProperties,
        name="scalargroups",
        description="The collection of loaded scalargroups")
    index_scalargroups = IntProperty(
        name="scalargroup index",
        description="index of the scalargroups collection",
        default=0,
        min=0)
    labelgroups = CollectionProperty(
        type=LabelGroupProperties,
        name="labelgroups",
        description="The collection of loaded labelgroups")
    index_labelgroups = IntProperty(
        name="labelgroup index",
        description="index of the labelgroups collection",
        default=0,
        min=0)

    colourtype = EnumProperty(
        name="colourtype",
        description="Apply this colour method",
        items=[("basic", "basic",
                "Switch to basic material", 1),
               ("directional", "directional",
                "Switch to directional colour-coding", 2)],
        update=material_enum_update)
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR",
        update=material_update)

    rendertype = EnumProperty(
        name="rendertype",
        description="Surface or volume rendering of texture",
        items=[("SURFACE", "Surface",
                "Switch to surface rendering", 0),
               ("VOLUME", "Volume",
                "Switch to volume rendering", 2)],
        update=rendertype_enum_update,
        default="VOLUME")

    range = FloatVectorProperty(
        name="Range",
        description="The original min-max in the data",
        default=(0, 0),
        size=2,
        precision=4)
    colourmap_enum = EnumProperty(
        name="colourmap",
        description="Apply this colour map",
        items=[("greyscale", "greyscale", "greyscale", 1),
               ("jet", "jet", "jet", 2),
               ("hsv", "hsv", "hsv", 3),
               ("hot", "hot", "hot", 4),
               ("cool", "cool", "cool", 5),
               ("spring", "spring", "spring", 6),
               ("summer", "summer", "summer", 7),
               ("autumn", "autumn", "autumn", 8),
               ("winter", "winter", "winter", 9),
               ("parula", "parula", "parula", 10)],
        default="greyscale",
        update=colourmap_enum_update)
    nn_elements = CollectionProperty(
        type=ColorRampProperties,
        name="nn_elements",
        description="The non-normalized color stops")
    index_nn_elements = IntProperty(
        name="nn_element index",
        description="Index of the non-normalized color stops",
        default=0,
        min=0)
    showcolourbar = BoolProperty(
        name="Render colourbar",
        description="Show/hide colourbar in rendered image",
        default=False)
    colourbar_placement = EnumProperty(
        name="Colourbar placement",
        description="Choose where to show the colourbar",
        default="top-right",
        items=[("top-right", "top-right",
                "Place colourbar top-right"),
               ("top-left", "top-left",
                "Place colourbar top-left"),
               ("bottom-right", "bottom-right",
                "Place colourbar bottom-right"),
               ("bottom-left", "bottom-left",
                "Place colourbar bottom-left")])  # update=colourbar_update
    colourbar_size = FloatVectorProperty(
        name="size",
        description="Set the size of the colourbar",
        default=[0.25, 0.05],
        size=2, min=0., max=1.)
    colourbar_position = FloatVectorProperty(
        name="position",
        description="Set the position of the colourbar",
        default=[1., 1.],
        size=2, min=-1., max=1.)
    textlabel_colour = FloatVectorProperty(
        name="Textlabel colour",
        description="Pick a colour",
        default=[1.0, 1.0, 1.0],
        subtype="COLOR")
    textlabel_placement = EnumProperty(
        name="Textlabel placement",
        description="Choose where to show the label",
        default="out",
        items=[("out", "out", "Place labels outside"),
               ("in", "in", "Place labels inside")])  # update=textlabel_update
    textlabel_size = FloatProperty(
        name="Textlabel size",
        description="Set the size of the textlabel (relative to colourbar)",
        default=0.5,
        min=0.,
        max=1.)

    slicebox = StringProperty(
        name="Slicebox",
        description="Name of slicebox",
        default="box")
    slicethickness = FloatVectorProperty(
        name="Slice thickness",
        description="The thickness of the slices",
        default=(1.0, 1.0, 1.0),
        size=3,
        precision=4,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceposition = FloatVectorProperty(
        name="Slice position",
        description="The position of the slices",
        default=(0.5, 0.5, 0.5),
        size=3,
        precision=4,
        min=0,
        max=1,
        subtype="TRANSLATION",
        update=slices_update)
    sliceangle = FloatVectorProperty(
        name="Slice position",
        description="The position of the slices",
        default=(0.0, 0.0, 0.0),
        size=3,
        precision=4,
        min=-1.5708,
        max=1.5708,
        subtype="TRANSLATION",
        update=slices_update)

    texdir = StringProperty(
        name="Texture directory",
        description="The directory with textures",
        subtype="DIR_PATH",
        update=texture_directory_update)
    texformat = EnumProperty(
        name="Volume texture file format",
        description="Choose a format to save volume textures",
        default="IMAGE_SEQUENCE",
        items=[("IMAGE_SEQUENCE", "IMAGE_SEQUENCE", "IMAGE_SEQUENCE", 0),
               ("STRIP", "STRIP", "STRIP", 1),
               ("RAW_8BIT", "RAW_8BIT", "RAW_8BIT", 2)])

    matname = StringProperty(
        name="Material name",
        description="The name of the scalar overlay")
    texname = StringProperty(
        name="Texture name",
        description="The name of the scalar overlay")


class CameraProperties(PropertyGroup):
    """Properties of cameras."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the camera",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for preset",
        default="CAMERA_DATA")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the camera is used for rendering",
        default=True)

    cam_view = FloatVectorProperty(
        name="Numeric input",
        description="Setting of the LR-AP-IS viewpoint of the camera",
        default=[2.88675, 2.88675, 2.88675],
        size=3,
        subtype="TRANSLATION")

    cam_view_enum_LR = EnumProperty(
        name="Camera LR viewpoint",
        description="Choose a LR position for the camera",
        default="Right",
        items=[("Left", "L", "Left", 0),
               ("Centre", "C", "Centre", 1),
               ("Right", "R", "Right", 2)],
        update=cam_view_enum_XX_update)

    cam_view_enum_AP = EnumProperty(
        name="Camera AP viewpoint",
        description="Choose a AP position for the camera",
        default="Anterior",
        items=[("Anterior", "A", "Anterior", 0),
               ("Centre", "C", "Centre", 1),
               ("Posterior", "P", "Posterior", 2)],
        update=cam_view_enum_XX_update)

    cam_view_enum_IS = EnumProperty(
        name="Camera IS viewpoint",
        description="Choose a IS position for the camera",
        default="Superior",
        items=[("Inferior", "I", "Inferior", 0),
               ("Centre", "C", "Centre", 1),
               ("Superior", "S", "Superior", 2)],
        update=cam_view_enum_XX_update)

    cam_distance = FloatProperty(
        name="Camera distance",
        description="Relative distance of the camera (to bounding box)",
        default=5,
        min=0,
        update=cam_view_enum_XX_update)

    trackobject = EnumProperty(
        name="Track object",
        description="Choose an object to track with the camera",
        items=trackobject_enum_callback,
        update=trackobject_enum_update)


class LightsProperties(PropertyGroup):
    """Properties of light."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the lights",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for preset",
        default="OUTLINER_OB_LAMP")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the light is rendered",
        default=True,
        update=light_update)

    type = EnumProperty(
        name="Light type",
        description="type of lighting",
        items=[("PLANE", "PLANE", "PLANE", 1),
               ("POINT", "POINT", "POINT", 2),
               ("SUN", "SUN", "SUN", 3),
               ("SPOT", "SPOT", "SPOT", 4),
               ("HEMI", "HEMI", "HEMI", 5),
               ("AREA", "AREA", "AREA", 6)],
        default="SPOT",
        update=light_update)
    colour = FloatVectorProperty(
        name="Colour",
        description="Colour of the light",
        default=[1.0, 1.0, 1.0],
        subtype="COLOR",
        update=light_update)
    strength = FloatProperty(
        name="Strength",
        description="Strength of the light",
        default=1,
        min=0,
        update=light_update)
    size = FloatVectorProperty(
        name="Size",
        description="Relative size of the plane light (to bounding box)",
        size=2,
        default=[1.0, 1.0],
        update=light_update)
    location = FloatVectorProperty(
        name="Location",
        description="",
        default=[3.88675, 2.88675, 2.88675],
        size=3,
        subtype="TRANSLATION")


class TableProperties(PropertyGroup):
    """Properties of table."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the table",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for preset",
        default="SURFACE_DATA")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the overlay is rendered",
        default=False,
        update=table_update)
    beautified = BoolProperty(
        name="Beautify",
        description="",
        default=True)

    colourtype = EnumProperty(
        name="colourtype",
        description="Apply this colour method",
        items=[("basic", "basic",
                "Switch to basic material", 1),
               ("directional", "directional",
                "Switch to directional colour-coding", 2)],
        update=material_enum_update)
    colourpicker = FloatVectorProperty(
        name="",
        description="Pick a colour",
        default=[1.0, 0.0, 0.0],
        subtype="COLOR",
        update=material_update)

    scale = FloatVectorProperty(
        name="Table scale",
        description="Relative size of the table",
        default=[4.0, 4.0, 1.0],
        subtype="TRANSLATION")
    location = FloatVectorProperty(
        name="Table location",
        description="Relative location of the table",
        default=[0.0, 0.0, -1.0],
        subtype="TRANSLATION")


class AnimationProperties(PropertyGroup):
    """Properties of table."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the animation",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for animation",
        default="RENDER_ANIMATION")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the object passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the animation is rendered",
        default=True)

    animationtype = EnumProperty(
        name="Animation type",
        description="Switch between animation types",
        items=[("CameraPath", "Trajectory", "Animate a camera trajectory", 1),
               ("Slices", "Slices", "Animate voxelvolume slices", 2),
               ("TimeSeries", "Time series", "Play a time series", 3)])

    frame_start = IntProperty(
        name="startframe",
        description="first frame of the animation",
        min=0,
        default=1,
        update=campaths_enum_update)
    frame_end = IntProperty(
        name="endframe",
        description="last frame of the animation",
        min=1,
        default=100,
        update=campaths_enum_update)
    repetitions = FloatProperty(
        name="repetitions",
        description="number of repetitions",
        default=1,
        update=campaths_enum_update)
    offset = FloatProperty(
        name="offset",
        description="offset",
        default=0,
        update=campaths_enum_update)

    anim_block = IntVectorProperty(
        name="anim block",
        description="",
        size=2,
        default=[1, 100])

    reverse = BoolProperty(
        name="Reverse",
        description="Toggle direction of trajectory traversal",
        default=False,
        update=direction_toggle_update)

    campaths_enum = EnumProperty(
        name="Camera trajectory",
        description="Choose the camera trajectory",
        items=campaths_enum_callback,
        update=campaths_enum_update)
    tracktype = EnumProperty(
        name="Tracktype",
        description="Camera rotation options",
        items=[("TrackNone", "None", "Use the camera rotation property", 0),
               ("TrackCentre", "Centre", "Track the preset centre", 1),
               ("TrackPath", "Path", "Orient along the trajectory", 2)],
        default="TrackCentre",
        update=tracktype_enum_update)
    pathtype = EnumProperty(
        name="Pathtype",
        description="Trajectory types for the camera animation",
        items=[("Circular", "Circular",
                "Circular trajectory from camera position", 0),
               ("Streamline", "Streamline",
                "Curvilinear trajectory from a streamline", 1),
               ("Select", "Select",
                "Curvilinear trajectory from curve", 2),
               ("Create", "Create",
                "Create a path from camera positions", 3)],
        default="Circular")

    axis = EnumProperty(
        name="Animation axis",
        description="switch between animation axes",
        items=[("X", "X", "X", 0),
               ("Y", "Y", "Y", 1),
               ("Z", "Z", "Z", 2)],
        default="Z")

    anim_tract = EnumProperty(
        name="Animation streamline",
        description="Select tract to animate",
        items=tracts_enum_callback)
    spline_index = IntProperty(
        name="streamline index",
        description="index of the streamline to animate",
        min=0,
        default=0)

    anim_curve = EnumProperty(
        name="Animation curves",
        description="Select curve to animate",
        items=curves_enum_callback)

    anim_surface = EnumProperty(
        name="Animation surface",
        description="Select surface to animate",
        items=surfaces_enum_callback)
    anim_timeseries = EnumProperty(
        name="Animation timeseries",
        description="Select timeseries to animate",
        items=timeseries_enum_callback)

    anim_voxelvolume = EnumProperty(
        name="Animation voxelvolume",
        description="Select voxelvolume to animate",
        items=voxelvolumes_enum_callback)
    sliceproperty = EnumProperty(
        name="Property to animate",
        description="Select property to animate",
        items=[("Thickness", "Thickness", "Thickness", 0),
               ("Position", "Position", "Position", 1),
               ("Angle", "Angle", "Angle", 2)],
        default="Position")

    timeseries_object = EnumProperty(
        name="Object",
        description="Select object to animate",
        items=timeseries_object_enum_callback)

    cnsname = StringProperty(
        name="Constraint Name",
        description="Name of the campath constraint",
        default="")

    # TODO: TimeSeries props


# class CamPointProperties(PropertyGroup):
#
#     location = FloatVectorProperty(
#         name="campoint",
#         description="...",
#         default=[0.0, 0.0, 0.0],
#         subtype="TRANSLATION")


class CamPathProperties(PropertyGroup):
    """Properties of a camera path."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the camera path",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    icon = StringProperty(
        name="Icon",
        description="Icon for camera path",
        default="CAMERA_DATA")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the camera path passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the camera path is rendered",
        default=True)
#
#     bezier_points = CollectionProperty(
#         type=CamPointProperties,
#         name="campoints",
#         description="The collection of camera positions")
#     index_bezier_points = IntProperty(
#         name="campoint index",
#         description="index of the campoints collection",
#         default=0,
#         min=0)


class PresetProperties(PropertyGroup):
    """Properties of a preset."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the preset",
        update=update_name)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
#     filepath = StringProperty(
#         name="Filepath",
#         description="The filepath to the preset")
    icon = StringProperty(
        name="Icon",
        description="Icon for preset",
        default="CAMERA_DATA")
    is_valid = BoolProperty(
        name="Is Valid",
        description="Indicates if the preset passed validity checks",
        default=True)
    is_rendered = BoolProperty(
        name="Is Rendered",
        description="Indicates if the preset is rendered",
        default=True)

    centre = StringProperty(
        name="Centre",
        description="Scene centre",
        default="PresetCentre")
    box = StringProperty(
        name="Box",
        description="Scene box",
        default="PresetBox")
    cam = StringProperty(
        name="Camera",
        description="Scene camera",
        default="PresetCam")
    lightsempty = StringProperty(
        name="LightsEmpty",
        description="Scene lights empty",
        default="PresetLights")
    dims = FloatVectorProperty(
        name="dims",
        description="Dimension of the scene",
        default=[100, 100, 100],
        subtype="TRANSLATION")

    cameras = CollectionProperty(
        type=CameraProperties,
        name="cameras",
        description="The collection of loaded cameras")
    index_cameras = IntProperty(
        name="camera index",
        description="index of the cameras collection",
        default=0,
        min=0)
    lights = CollectionProperty(
        type=LightsProperties,
        name="lights",
        description="The collection of loaded lights")
    index_lights = IntProperty(
        name="light index",
        description="index of the lights collection",
        default=0,
        min=0)
    tables = CollectionProperty(
        type=TableProperties,
        name="tables",
        description="The collection of loaded tables")
    index_tables = IntProperty(
        name="table index",
        description="index of the tables collection",
        default=0,
        min=0)
    animations = CollectionProperty(
        type=AnimationProperties,
        name="animations",
        description="The collection of animations")
    index_animations = IntProperty(
        name="animation index",
        description="index of the animations collection",
        default=0,
        min=0)

    lights_enum = EnumProperty(
        name="Light switch",
        description="switch between lighting modes",
        items=[("Key", "Key", "Use Key lighting only", 1),
               ("Key-Back-Fill", "Key-Back-Fill",
                "Use Key-Back-Fill lighting", 2),
               ("Free", "Free", "Set up manually", 3)],
        default="Key")

    frame_start = IntProperty(
        name="startframe",
        description="first frame of the animation",
        min=1,
        default=1)
    frame_end = IntProperty(
        name="endframe",
        description="last frame of the animation",
        min=2,
        default=100)


class NeuroBlenderProperties(PropertyGroup):
    """Properties for the NeuroBlender panel."""

    is_enabled = BoolProperty(
        name="Show/hide NeuroBlender",
        description="Show/hide the NeuroBlender panel contents",
        default=True)

    projectdir = StringProperty(
        name="Project directory",
        description="The path to the NeuroBlender project",
        subtype="DIR_PATH",
        default=os.path.expanduser('~'))

    try:
        import nibabel as nib
        nib_valid = True
        nib_dir = os.path.dirname(nib.__file__)
        esp_path = os.path.dirname(nib_dir)
    except:
        nib_valid = False
        esp_path = ""

    nibabel_valid = BoolProperty(
        name="nibabel valid",
        description="Indicates whether nibabel has been detected",
        default=nib_valid)
    esp_path = StringProperty(
        name="External site-packages",
        description=""""
            The path to the site-packages directory
            of an equivalent python version with nibabel installed
            e.g. using:
            >>> conda create --name blender python=3.5.1
            >>> source activate blender
            >>> pip install git+git://github.com/nipy/nibabel.git@master
            on Mac this would be the directory:
            <conda root dir>/envs/blender/lib/python3.5/site-packages
            """,
        default=esp_path,
        subtype="DIR_PATH",
        update=esp_path_update)

    mode = EnumProperty(
        name="mode",
        description="switch between NeuroBlender modes",
        items=[("artistic", "artistic", "artistic", 1),
               ("scientific", "scientific", "scientific", 2)],
        default="artistic",
        update=mode_enum_update)

    engine = EnumProperty(
        name="engine",
        description="""Engine to use for rendering""",
        items=[("BLENDER_RENDER", "Blender Render",
                "Blender Render: required for voxelvolumes", 0),
#                ("BLENDER_GAME", "Blender Game", "Blender Game", 1),
               ("CYCLES", "Cycles Render",
                "Cycles Render: required for most overlays", 2)],
        update=engine_update)

    texformat = EnumProperty(
        name="Volume texture file format",
        description="Choose a format to save volume textures",
        default="IMAGE_SEQUENCE",
        items=[("IMAGE_SEQUENCE", "IMAGE_SEQUENCE", "IMAGE_SEQUENCE", 0),
               ("STRIP", "STRIP", "STRIP", 1),
               ("RAW_8BIT", "RAW_8BIT", "RAW_8BIT", 2)])
    texmethod = IntProperty(
        name="texmethod",
        description="",
        default=1,
        min=1, max=4)
    uv_resolution = IntProperty(
        name="utexture resolution",
        description="the resolution of baked textures",
        default=4096,
        min=1)
    uv_bakeall = BoolProperty(
        name="Bake all",
        description="Bake single or all scalars in a group",
        default=True)

    advanced = BoolProperty(
        name="Advanced mode",
        description="Advanced NeuroBlender layout",
        default=False)

    verbose = BoolProperty(
        name="Verbose",
        description="Verbose reporting",
        default=False)

    show_transform = BoolProperty(
        name="Transform",
        default=False,
        description="Show/hide the object's transform options")
    show_material = BoolProperty(
        name="Material",
        default=False,
        description="Show/hide the object's materials options")
    show_slices = BoolProperty(
        name="Slices",
        default=False,
        description="Show/hide the object's slice options")
    show_info = BoolProperty(
        name="Info",
        default=False,
        description="Show/hide the object's info")
    show_overlay_material = BoolProperty(
        name="Overlay material",
        default=False,
        description="Show/hide the object's overlay material")
    show_overlay_slices = BoolProperty(
        name="Overlay slices",
        default=False,
        description="Show/hide the object's overlay slices")
    show_overlay_info = BoolProperty(
        name="Overlay info",
        default=False,
        description="Show/hide the overlay's info")
    show_items = BoolProperty(
        name="Items",
        default=False,
        description="Show/hide the group overlay's items")
    show_itemprops = BoolProperty(
        name="Item properties",
        default=True,
        description="Show/hide the properties of the item")
    show_additional = BoolProperty(
        name="Additional options",
        default=False,
        description="Show/hide the object's additional options")
    show_bounds = BoolProperty(
        name="Bounds",
        default=False,
        description="Show/hide the preset's centre and dimensions")
    show_cameras = BoolProperty(
        name="Camera",
        default=False,
        description="Show/hide the preset's camera properties")
    show_lights = BoolProperty(
        name="Lights",
        default=False,
        description="Show/hide the preset's lights properties")
    show_key = BoolProperty(
        name="Key",
        default=False,
        description="Show/hide the Key light properties")
    show_back = BoolProperty(
        name="Back",
        default=False,
        description="Show/hide the Back light properties")
    show_fill = BoolProperty(
        name="Fill",
        default=False,
        description="Show/hide the Fill light properties")
    show_tables = BoolProperty(
        name="Table",
        default=False,
        description="Show/hide the preset's table properties")
    show_animations = BoolProperty(
        name="Animation",
        default=False,
        description="Show/hide the preset's animations")
    show_timings = BoolProperty(
        name="Timings",
        default=True,
        description="Show/hide the animation's timings")
    show_animcamerapath = BoolProperty(
        name="CameraPath",
        default=True,
        description="Show/hide the animation's camera path properties")
    show_animslices = BoolProperty(
        name="Slices",
        default=True,
        description="Show/hide the animation's slice properties")
    show_timeseries = BoolProperty(
        name="Time Series",
        default=True,
        description="Show/hide the animation's time series properties")
    show_camerapath = BoolProperty(
        name="Camera trajectory",
        default=True,
        description="Show/hide the animation's camera path properties")
    show_tracking = BoolProperty(
        name="Tracking",
        default=False,
        description="Show/hide the camera path's tracking properties")
    show_newpath = BoolProperty(
        name="New trajectory",
        default=False,
        description="Show/hide the camera trajectory generator")
    show_points = BoolProperty(
        name="Points",
        default=False,
        description="Show/hide the camera path points")
    show_unwrap = BoolProperty(
        name="Unwrap",
        default=False,
        description="Show/hide the unwrapping options")

    tracts = CollectionProperty(
        type=TractProperties,
        name="tracts",
        description="The collection of loaded tracts")
    index_tracts = IntProperty(
        name="tract index",
        description="index of the tracts collection",
        default=0,
        min=0)
    surfaces = CollectionProperty(
        type=SurfaceProperties,
        name="surfaces",
        description="The collection of loaded surfaces")
    index_surfaces = IntProperty(
        name="surface index",
        description="index of the surfaces collection",
        default=0,
        min=0)
    voxelvolumes = CollectionProperty(
        type=VoxelvolumeProperties,
        name="voxelvolumes",
        description="The collection of loaded voxelvolumes")
    index_voxelvolumes = IntProperty(
        name="voxelvolume index",
        description="index of the voxelvolumes collection",
        default=0,
        min=0)

    presets = CollectionProperty(
        type=PresetProperties,
        name="presets",
        description="The collection of presets")
    index_presets = IntProperty(
        name="preset index",
        description="index of the presets",
        default=0,
        min=0)
    presets_enum = EnumProperty(
        name="presets",
        description="switch between presets",
        items=presets_enum_callback,
        update=presets_enum_update)

    campaths = CollectionProperty(
        type=CamPathProperties,
        name="camera paths",
        description="The collection of camera paths")
    index_campaths = IntProperty(
        name="camera path index",
        description="index of the camera paths collection",
        default=0,
        min=0)

    objecttype = EnumProperty(
        name="object type",
        description="switch between object types",
        items=[("tracts", "tracts", "List the tracts", 1),
               ("surfaces", "surfaces", "List the surfaces", 2),
               ("voxelvolumes", "voxelvolumes", "List the voxelvolumes", 3)],
        default="tracts")
    overlaytype = EnumProperty(
        name="overlay type",
        description="switch between overlay types",
        items=overlay_enum_callback)


# @persistent
# def projectdir_update(dummy):
#     """"""
#
#     scn = bpy.context.scene
#     nb = scn.nb
#
# #     nb.projectdir = os.path.
#
# bpy.app.handlers.load_post(projectdir_update)

# @persistent
# def engine_driver_handler(dummy):
#     """"""
#
#     engine_driver()
#
# bpy.app.handlers.load_post.append(engine_driver_handler)

# =========================================================================== #


def register():
    bpy.utils.register_module(__name__)
    bpy.types.Scene.nb = PointerProperty(type=NeuroBlenderProperties)


def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.Scene.nb

if __name__ == "__main__":
    register()
