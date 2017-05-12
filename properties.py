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


"""The NeuroBlender properties module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements all of NeuroBlender's custom property classes,
as well as there callback and update functions.
"""

import os
import re
from glob import glob

import mathutils

import bpy
from bpy.types import PropertyGroup
from bpy.props import (BoolProperty,
                       StringProperty,
                       CollectionProperty,
                       EnumProperty,
                       FloatVectorProperty,
                       FloatProperty,
                       IntProperty,
                       IntVectorProperty,
                       PointerProperty)
from bpy.app.handlers import persistent

from . import (materials as nb_ma,
               renderpresets as nb_rp,
               utils as nb_ut)


# ========================================================================== #
# handler functions
# ========================================================================== #


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


@persistent
def index_scalars_handler(dummy):
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
                                                         nb.settingprops.texmethod)

bpy.app.handlers.frame_change_pre.append(index_scalars_handler)


@persistent
def init_settings_handler(dummy):
    """Force update on NeuroBlender settings."""

    scn = bpy.context.scene
    nb = scn.nb

    nb.settingprops.projectdir = nb.settingprops.projectdir
    nb.settingprops.esp_path = nb.settingprops.esp_path
    nb.settingprops.mode = nb.settingprops.mode
    nb.settingprops.engine = nb.settingprops.engine
    nb.settingprops.texformat = nb.settingprops.texformat
    nb.settingprops.texmethod = nb.settingprops.texmethod
    nb.settingprops.uv_resolution = nb.settingprops.uv_resolution
    nb.settingprops.advanced = nb.settingprops.advanced
    nb.settingprops.verbose = nb.settingprops.verbose

bpy.app.handlers.load_post.append(init_settings_handler)


# ========================================================================== #
# update and callback functions: settings
# ========================================================================== #


def engine_update(self, context):
    """Update materials when switching between engines."""

    scn = context.scene
    nb = scn.nb

    for mat in bpy.data.materials:
        mat.use_nodes = nb.settingprops.engine == "CYCLES"
        if nb.settingprops.engine.startswith("BLENDER"):
            nb_ma.CR2BR(mat)
        else:
            nb_ma.BR2CR(mat)

    scn.render.engine = nb.settingprops.engine
    # TODO: handle lights


def engine_driver():

    scn = bpy.context.scene
    nb = scn.nb

    driver = nb.driver_add("engine", -1).driver
    driver.type = 'AVERAGE'

    nb_rp.create_var(driver, "type", 'SINGLE_PROP', 'SCENE', scn, "render.engine")


def esp_path_update(self, context):
    """Add external site-packages path to sys.path."""

    nb_ut.add_path(self.esp_path)


def mode_enum_update(self, context):
    """Perform actions for updating mode."""

    # TODO: switch colourbars

    scn = context.scene
    nb = scn.nb

    for mat in bpy.data.materials:
        nb_ma.switch_mode_mat(mat, self.mode)

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
                                 nb.settingprops.mode, nb_cam.cam_view)


def managecmap_update(self, context):
    """Generate/delete dummy objects to manage colour maps."""

    scn = context.scene
    nb = scn.nb

    def gen_dummies(name="manage_colourmaps"):

        ivv = bpy.types.NB_OT_import_voxelvolumes
        cube = ivv.voxelvolume_box_ob([2, 2, 2], "SliceBox")
        cube.hide = cube.hide_render = True
        cube.name = cube.data.name = name
        bpy.data.materials.new(name)
        mat = bpy.data.materials.get(name)
        mat.volume.density = 0

        bpy.data.textures.new(name, type='DISTORTED_NOISE')
        tex = bpy.data.textures.get(name)
        tex.use_preview_alpha = True
        tex.use_color_ramp = True

        texslot = mat.texture_slots.add()
        texslot.texture = tex

        texslot.use_map_density = True
        texslot.texture_coords = 'ORCO'
        texslot.use_map_emission = True

        cube.data.materials.append(mat)

    def del_dummies(name="manage_colourmaps"):

        tex = bpy.data.textures.get(name)
        bpy.data.textures.remove(tex)
        mat = bpy.data.materials.get(name)
        bpy.data.materials.remove(mat)
        me = bpy.data.meshes.get(name)
        bpy.data.meshes.remove(me)

    name="manage_colourmaps"

    if self.show_manage_colourmaps:
        gen_dummies(name)

        # FIXME: this is unsafe
        cr_parentpath = "bpy.data.textures['{}']".format(name)
        cr_path = '{}.color_ramp'.format(cr_parentpath)
        context.scene.nb.cr_path = cr_path

        # load preset
        cr_path = '{}.color_ramp'.format(cr_parentpath)
        nb.cr_path = cr_path

        preset_class = getattr(bpy.types, "OBJECT_MT_colourmap_presets")
        preset_class.bl_label = bpy.path.display_name("Colourmap Presets")

    else:
        del_dummies(name)


# ========================================================================== #
# update and callback functions: animations
# ========================================================================== #


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
#     sgs = find_ts_scalargroups(self)
        items = [(scalargroup.name, scalargroup.name, "List the timeseries", i)
                 for i, scalargroup in enumerate(sgs)]

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


# ========================================================================== #
# update and callback functions: scene presets
# ========================================================================== #


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

#     cam_view_update(cam, centre, self.cam_view, nb_preset.dims)
    cam.location = self.cam_view

    scn.frame_set(0)


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


# ========================================================================== #
# update and callback functions: overlays
# ========================================================================== #


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


def index_scalars_update_func(group=None):
    """Switch views on updating overlay index."""

    scn = bpy.context.scene
    nb = scn.nb

    if group is None:
        group = nb_ut.active_nb_overlay()[0]

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
                                                     nb.settingprops.texmethod)


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
        group = nb_ut.active_nb_overlay()[0]

    try:
        label = group.labels[group.index_labels]
    except IndexError:
        pass
    else:
        name = label.name

        if "surfaces" in group.path_from_id():
            vg_idx = ob.vertex_groups.find(name)
            ob.vertex_groups.active_index = vg_idx


# ========================================================================== #
# update and callback functions: base geometry
# ========================================================================== #


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


def voxelvolumes_enum_callback(self, context):
    """Populate the enum based on available options."""

    scn = context.scene
    nb = scn.nb

    items = [(vvol.name, vvol.name, "List the voxelvolumes", i)
             for i, vvol in enumerate(nb.voxelvolumes)]

    return items


def sformfile_update(self, context):
    """Set the sform transformation matrix for the object."""

    try:
        ob = bpy.data.objects[self.name]
    except:
        pass
    else:
        sformfile = bpy.path.abspath(self.sformfile)
        affine = nb_ut.read_affine_matrix(sformfile)
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


def is_yoked_bool_update(self, context):
    """Add or remove drivers linking voxelvolume and overlay."""

    nb_ob = nb_ut.active_nb_object()[0]
    for prop in ['slicethickness', 'sliceposition', 'sliceangle']:
        for idx in range(0, 3):
            if self.is_yoked:
                ivv = bpy.types.NB_OT_import_voxelvolumes
                ivv.voxelvolume_slice_drivers_yoke(nb_ob, self, prop, idx)
            else:
                self.driver_remove(prop, idx)


# ========================================================================== #
# update and callback functions: general
# ========================================================================== #


def name_update(self, context):
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


# ========================================================================== #
# update and callback functions: materials
# ========================================================================== #


def material_update(self, context):
    """Assign a new preset material to the object."""

    scn = context.scene
    nb = scn.nb

    mat = bpy.data.materials[self.name]
    if nb.settingprops.engine.startswith("BLENDER"):
        nb_ma.CR2BR(mat)


def material_enum_update(self, context):
    """Assign a new preset material to the object."""

    mat = bpy.data.materials[self.name]
    nb_ma.link_innode(mat, self.colourtype)


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
                    ivv = bpy.types.NB_OT_import_voxelvolumes
                    ivv.voxelvolume_slice_drivers_surface(self, ts,
                                                          idx, "scale")
                    ivv.voxelvolume_slice_drivers_surface(self, ts,
                                                          idx, "offset")


def colourmap_enum_callback(self, context):
    """Populate the enum based on available options."""

    def order_cmaps(mapnames, pref_order):
        """Order a list starting with with a prefered ordering."""

        mapnames_ordered = []
        for mapname in pref_order:
            if mapname in mapnames:
                mapnames_ordered.append(mapname)
                mapnames.pop(mapnames.index(mapname))
        if mapnames:
            mapnames_ordered += mapnames

        return mapnames_ordered

    cmap_dir = os.path.join("presets", "neuroblender_colourmaps")
    preset_path = bpy.utils.user_resource('SCRIPTS', cmap_dir, create=False)
    files = glob(os.path.join(preset_path, '*.py'))

    mapnames = [os.path.splitext(os.path.basename(f))[0]
                for i, f in enumerate(files)]

    pref_order = ["grey", "jet", "hsv", "hot", "cool",
                  "spring", "summer", "autumn", "winter",
                  "parula"]
    mapnames = order_cmaps(mapnames, pref_order)

    items = []
    for i, mapname in enumerate(mapnames):
        displayname = bpy.path.display_name(mapname)
        items.append((mapname, displayname, "", i))

    return items


def colourmap_enum_update(self, context):
    """Assign a new colourmap to the object."""

    scn = context.scene
    nb = scn.nb

    nb_ob = nb_ut.active_nb_object()[0]
    if hasattr(nb_ob, 'slicebox'):
        cr = bpy.data.textures[self.name].color_ramp
        cr_parentpath = 'bpy.data.textures["{}"]'.format(self.name)
    else:
        if hasattr(nb_ob, "nstreamlines"):
            ng = bpy.data.node_groups.get("TractOvGroup")
            cr = ng.nodes["ColorRamp"].color_ramp
            ng_path = 'bpy.data.node_groups["TractOvGroup"]'
            # FIXME: include self.name
            cr_parentpath = '{}.nodes["ColorRamp"]'.format(ng_path)
        elif hasattr(nb_ob, "sphere"):
            nt = bpy.data.materials[self.name].node_tree
            cr = nt.nodes["ColorRamp"].color_ramp
            nt_path = 'bpy.data.materials["{}"].node_tree'.format(self.name)
            cr_parentpath = '{}.nodes["ColorRamp"]'.format(nt_path)

    colourmap = self.colourmap_enum

    # load preset
    cr_path = '{}.color_ramp'.format(cr_parentpath)
    nb.cr_path = cr_path
    menu_idname = "OBJECT_MT_colourmap_presets"

    cmap_dir = os.path.join("presets","neuroblender_colourmaps")
    preset_path = bpy.utils.user_resource('SCRIPTS', cmap_dir, create=False)
    filepath = os.path.join(preset_path, '{}.py'.format(colourmap))

    bpy.ops.script.execute_preset_cr(filepath=filepath,
                                     menu_idname=menu_idname,
                                     cr_path=cr_path)


def texture_directory_update(self, context):
    """Update the texture."""

    if "surfaces" in self.path_from_id():
        nb_ma.load_surface_textures(self.name, self.texdir, len(self.scalars))
    elif "voxelvolumes" in self.path_from_id():
        pass  # TODO


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


# ========================================================================== #
# NeuroBlender custom properties
# ========================================================================== #


class SettingsProperties(PropertyGroup):
    """Properties for the NeuroBlender settings."""

    sp_presetlabel = StringProperty(
        name="SP label",
        default="")

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


class CameraProperties(PropertyGroup):
    """Properties of cameras."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the camera",
        update=name_update)
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
        update=name_update)
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
        update=name_update)
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


class CamPathProperties(PropertyGroup):
    """Properties of a camera path."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the camera path",
        update=name_update)
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


class AnimationProperties(PropertyGroup):
    """Properties of table."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the animation",
        update=name_update)
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


class PresetProperties(PropertyGroup):
    """Properties of a preset."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the preset",
        update=name_update)
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


class ColorRampProperties(PropertyGroup):
    """Custom properties of color ramps."""

    name = StringProperty(
        name="Name",
        description="The name of the color stop",
        update=name_update)
    name_mem = StringProperty(
        name="NameMem",
        description="Memory for updating name")
    nn_position = FloatProperty(
        name="nn_position",
        description="The non-normalized position of the color stop",
        default=0,
        precision=4)

    def calc_nn_position(self, position, range):
        """Calculate the non-normalized positions of elements."""

        dmin = range[0]
        dmax = range[1]
        drange = dmax-dmin
        self.nn_position = position * drange + dmin


class ScalarProperties(PropertyGroup):
    """Properties of scalar overlays."""

    name = StringProperty(
        name="Name",
        description="The name of the scalar overlay",
        update=name_update)
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
        items=colourmap_enum_callback,
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
        update=name_update)
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
        update=name_update)
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
        update=name_update)
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
        items=colourmap_enum_callback,
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
        update=name_update)
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
        items=colourmap_enum_callback,
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
        update=name_update)
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
        update=name_update)
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
        update=name_update)
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
    is_unwrapped = BoolProperty(
        name="Is unwrapped",
        description="Indicates if the surface has been unwrapped",
        default=False)


class VoxelvolumeProperties(PropertyGroup):
    """Properties of voxelvolumes."""

    name = StringProperty(
        name="Name",
        description="Specify a name for the voxelvolume (default: filename)",
        update=name_update)
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
        items=colourmap_enum_callback,
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


class NeuroBlenderProperties(PropertyGroup):
    """Properties for the NeuroBlender panel."""

    is_enabled = BoolProperty(
        name="Show/hide NeuroBlender",
        description="Show/hide the NeuroBlender panel contents",
        default=True)

    settingprops = PointerProperty(type=SettingsProperties)

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
    show_manage_colourmaps = BoolProperty(
        name="Manage colour maps",
        default=False,
        description="Show/hide the colour map management",
        update=managecmap_update)

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

    # TODO: move to elsewhere
    cr_keeprange = BoolProperty(
        name="Keep range",
        description="Keep/discard the current range of the colour ramp",
        default=True)

    cr_path = StringProperty(
        name="CR path")

    cm_presetlabel = StringProperty(
        name="CM label",
        default="Grey")

# @persistent
# def projectdir_update(dummy):
#     """"""
#
#     scn = bpy.context.scene
#     nb = scn.nb
#
# #     nb.settingprops.projectdir = os.path.
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
