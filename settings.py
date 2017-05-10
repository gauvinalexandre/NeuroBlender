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


"""The NeuroBlender settings module.

NeuroBlender is a Blender add-on to create artwork from neuroscientific data.
This module implements NeuroBlender configuration.
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
from bl_operators.presets import AddPresetBase, ExecutePreset

import os
import sys
from shutil import copy
import numpy as np
import mathutils
import re

from . import animations as nb_an
from . import base as nb_ba
from . import beautify as nb_be
from . import colourmaps as nb_cm
from . import imports as nb_im
from . import materials as nb_ma
from . import overlays as nb_ol
from . import panels as nb_pa
from . import renderpresets as nb_rp
from . import scenepresets as nb_sp
# from . import settings as nb_se
from . import utils as nb_ut

# from .materials import (CR2BR,
#                         BR2CR,
#                         switch_mode_mat)
# from .renderpresets import (create_var,
#                             switch_mode_preset)
# from .utils import add_path

# =========================================================================== #


# https://docs.blender.org/api/blender_python_api_2_77_0/bpy.types.Menu.html
class OBJECT_MT_setting_presets(Menu):
    bl_label = "NeuroBlender Settings Presets"
    bl_description = "Load a NeuroBlender Settings Preset"
    preset_subdir = "neuroblender"
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset


class AddPresetNeuroBlenderSettings(AddPresetBase, Operator):
    bl_idname = "nb.setting_presets"
    bl_label = "NeuroBlender Setting Presets"
    bl_description = "Add/Delete a NeuroBlender Settings Preset"
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
