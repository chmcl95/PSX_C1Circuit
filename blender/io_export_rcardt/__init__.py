bl_info = {
    "name": "RCARDT Model Import/Export (PS1 Racing Car Model)",
    "author": "Claude",
    "version": (1, 1, 0),
    "blender": (4, 2, 0),
    "location": "File > Import-Export > RCARDT Model (00000000)  |  "
                "Scene/Object/Material Properties > RCARDT panels",
    "description": "Import and export the RCARDT (00000000) PS1 car model "
                   "format used by C1 Circuit.",
    "category": "Import-Export",
}

import bpy

from . import rcardt_presets
from . import rcardt_props
from . import rcardt_editor
from . import export_rcardt
from . import import_rcardt

if "bpy" in locals():
    import importlib
    if "rcardt_format" in locals():
        importlib.reload(rcardt_format)
    if "rcardt_presets" in locals():
        importlib.reload(rcardt_presets)
    if "rcardt_props" in locals():
        importlib.reload(rcardt_props)
    if "rcardt_editor" in locals():
        importlib.reload(rcardt_editor)
    if "export_rcardt" in locals():
        importlib.reload(export_rcardt)
    if "import_rcardt" in locals():
        importlib.reload(import_rcardt)


def register():
    rcardt_props.register()
    rcardt_editor.register()
    export_rcardt.register()
    import_rcardt.register()


def unregister():
    import_rcardt.unregister()
    export_rcardt.unregister()
    rcardt_editor.unregister()
    rcardt_props.unregister()


if __name__ == "__main__":
    register()
