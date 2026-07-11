bl_info = {
    "name": "RCARDT Model Export (PS1 Racing Car Model)",
    "author": "Claude",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "File > Import-Export > RCARDT Model (00000000)  |  "
                "Object/Material Properties > RCARDT Node/Material Editor",
    "description": "Export Blender meshes to the RCARDT (00000000) PS1 car "
                   "model format used by C1 Circuit.",
    "category": "Import-Export",
}

import bpy

from . import rcardt_props
from . import rcardt_editor
from . import export_rcardt

if "bpy" in locals():
    import importlib
    if "rcardt_format" in locals():
        importlib.reload(rcardt_format)
    if "rcardt_props" in locals():
        importlib.reload(rcardt_props)
    if "rcardt_editor" in locals():
        importlib.reload(rcardt_editor)
    if "export_rcardt" in locals():
        importlib.reload(export_rcardt)


def register():
    rcardt_props.register()
    rcardt_editor.register()
    export_rcardt.register()


def unregister():
    export_rcardt.unregister()
    rcardt_editor.unregister()
    rcardt_props.unregister()


if __name__ == "__main__":
    register()
