import bpy

from . import rcardt_presets

# Blender keeps no reference to the strings a dynamic EnumProperty callback
# returns, so they have to stay alive here or the UI shows garbage.
_clut_enum_items = []


def preset_file_path(context=None):
    """The clut_presets.json this scene is working against.

    Importing a model points this at the car's own file; otherwise it is
    empty and the built-in slots apply.
    """
    context = context or bpy.context
    scene = getattr(context, "scene", None)
    if scene is None:
        return ""
    return scene.rcardt_clut_preset_file


def clut_preset_items(self, context):
    """CLUT slot list, read from the scene's clut_presets.json."""
    global _clut_enum_items
    table = rcardt_presets.get_table(preset_file_path(context))
    items = []
    for preset in table.presets:
        label = preset.name
        if preset.description:
            label = f"{preset.name} ({preset.description})"
        items.append((
            preset.name,
            label,
            f"Palette at VRAM ({preset.clut_x}, {preset.clut_y}); "
            f"the model stores X={preset.model_clut_x} Y={preset.clut_y}",
        ))
    items.append((
        rcardt_presets.MANUAL_ID,
        rcardt_presets.MANUAL_LABEL,
        "Ignore the slot list and write the raw CLUT X/Y fields below",
    ))
    _clut_enum_items = items
    return _clut_enum_items


class RCARDT_OT_ReloadPresets(bpy.types.Operator):
    """Re-read clut_presets.json from disk"""

    bl_idname = "rcardt.reload_clut_presets"
    bl_label = "Reload CLUT Slots"

    def execute(self, context):
        rcardt_presets.invalidate_cache()
        table = rcardt_presets.get_table(preset_file_path(context))
        self.report({'INFO'},
                    f"Reloaded {len(table.presets)} CLUT slot(s) from {table.source}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Object-level settings: which of the 4 fixed RCARDT nodes this object is,
# and its node-header position / rotation (independent of mesh vertex data).
# ---------------------------------------------------------------------------
class RCARDT_ObjectSetting(bpy.types.PropertyGroup):
    """Attached to bpy.types.Object. Assigns the object to one of the
    4 fixed RCARDT nodes and controls that node's header fields."""

    enabled: bpy.props.BoolProperty(
        name="Include in RCARDT Export",
        description="Treat this object as one of the 4 RCARDT nodes",
        default=False,
    )

    node_index: bpy.props.IntProperty(
        name="Node Index",
        description="Which of the 4 fixed RCARDT nodes this object fills "
                    "(0 = body, 1/2 = front wheels, 3 = rear wheels). The "
                    "game assumes this order and cannot take more nodes",
        default=0, min=0, max=3,
    )

    auto_transform: bpy.props.BoolProperty(
        name="Auto From Object Transform",
        description="Derive the node's position/rotation header fields "
                    "automatically from this object's Location/Rotation "
                    "instead of the manual fields below",
        default=True,
    )

    position: bpy.props.IntVectorProperty(
        name="Node Position",
        description="Node header position (game integer units), used only "
                    "when Auto From Object Transform is disabled",
        default=(0, 0, 0), size=3,
    )

    rotation: bpy.props.IntVectorProperty(
        name="Node Rotation",
        description="Node header rotation (game integer/angle units), used "
                    "only when Auto From Object Transform is disabled",
        default=(0, 0, 0), size=3,
    )

    ptr_mdl: bpy.props.IntProperty(
        name="ptr_mdl",
        description="Runtime-only pointer preserved from an imported file. "
                    "The game overwrites it on load; new models write 0",
        default=0,
    )


# ---------------------------------------------------------------------------
# Material-level settings: PS1 GPU polygon packet parameters for every
# Surface generated from faces using this material.
# ---------------------------------------------------------------------------
class RCARDT_MaterialSetting(bpy.types.PropertyGroup):
    """Attached to bpy.types.Material. Controls the PSX_GPU_COMMAND /
    CLUT / Texpage fields written for every Surface using this material."""

    color: bpy.props.IntVectorProperty(
        name="Flat Color",
        description="Surface flat color (0-255 per channel). The format "
                    "stores one color per surface, not per vertex",
        default=(128, 128, 128), min=0, max=255, size=3,
    )

    # --- PSX_GPU_COMMAND ---
    textured: bpy.props.BoolProperty(
        name="Textured",
        description="Enable texture mapping for this surface",
        default=True,
    )
    raw_texture: bpy.props.BoolProperty(
        name="Raw Texture",
        description="Ignore lighting/shading and use raw texture colors",
        default=False,
    )
    semi_transparent: bpy.props.BoolProperty(
        name="Semi Transparent",
        description="Enable semi-transparency blending. The palette also "
                    "needs its STP bit (0x8000) set and the pixels must not "
                    "be pure black, or nothing will be transparent",
        default=False,
    )
    gouraud: bpy.props.BoolProperty(
        name="Gouraud Shading",
        description="Mark surface as Gouraud shaded (this format still "
                    "only stores a single flat color per surface)",
        default=False,
    )
    render_type: bpy.props.IntProperty(
        name="Render Type",
        description="1 = polygon, 2 = line, 3 = rectangle. RCARDT models "
                    "only ever use 1",
        default=1, min=0, max=7,
    )

    # --- CLUT (Color Lookup Table location in VRAM) ---
    clut_preset: bpy.props.EnumProperty(
        name="CLUT Slot",
        description="Named palette slot from clut_presets.json. The same "
                    "slot drives the texture side in C1CircuitTool, so the "
                    "two cannot drift apart. Choose Manual for raw values",
        items=clut_preset_items,
    )
    clut_x: bpy.props.IntProperty(
        name="CLUT X (raw)",
        description="Raw CLUT X coordinate. Actual VRAM X = value * 16. "
                    "Only used when CLUT Slot is Manual",
        default=8, min=0, max=63,
    )
    clut_y: bpy.props.IntProperty(
        name="CLUT Y",
        description="CLUT Y coordinate in VRAM (0-511). Only used when "
                    "CLUT Slot is Manual",
        default=496, min=0, max=511,
    )

    # --- Texpage ---
    texpage_x: bpy.props.IntProperty(
        name="Texpage X (raw)",
        description="Raw texture page X. Actual VRAM X = value * 64",
        default=0, min=0, max=15,
    )
    texpage_y: bpy.props.IntProperty(
        name="Texpage Y (raw)",
        description="Raw texture page Y. Actual VRAM Y = value * 256",
        default=0, min=0, max=1,
    )
    semi_transparency_mode: bpy.props.EnumProperty(
        name="Semi Transparency Mode",
        items=[
            ('0', "B/2 + F/2", "50% back + 50% front"),
            ('1', "B + F", "Additive"),
            ('2', "B - F", "Subtractive"),
            ('3', "B + F/4", "Additive quarter front"),
        ],
        default='0',
    )
    texture_page_colors: bpy.props.EnumProperty(
        name="Texture Page Colors",
        items=[
            ('0', "4 bit (CLUT)", ""),
            ('1', "8 bit (CLUT)", ""),
            ('2', "15 bit", ""),
            ('3', "Reserved", ""),
        ],
        default='0',
    )
    texture_disable: bpy.props.BoolProperty(
        name="Texture Disable",
        description="Ignore the texture and use the flat color. This is the "
                    "way to get more than one color onto semi-transparent "
                    "faces",
        default=False,
    )

    # --- Raw passthrough / unknown fields, exposed for advanced tweaking ---
    unk_bit9: bpy.props.IntProperty(
        name="Unknown Texpage bit9-10", default=0, min=0, max=3,
    )
    unk_bit12: bpy.props.IntProperty(
        name="Unknown Texpage bit12-15", default=0, min=0, max=15,
    )

    # UI collapsible section flags
    show_command: bpy.props.BoolProperty(default=True)
    show_clut: bpy.props.BoolProperty(default=True)
    show_texpage: bpy.props.BoolProperty(default=False)
    show_advanced: bpy.props.BoolProperty(default=False)

    # -- helpers ---------------------------------------------------------
    def resolve_clut(self, context=None):
        """(clut_x_raw, clut_y) as written into 00000000.BIN."""
        if self.clut_preset == rcardt_presets.MANUAL_ID:
            return (self.clut_x, self.clut_y)
        table = rcardt_presets.get_table(preset_file_path(context))
        resolved = table.resolve(self.clut_preset)
        if resolved is None:
            # The slot was renamed or removed since this material was set up.
            # Fall back to the raw fields rather than silently writing the
            # wrong palette.
            return (self.clut_x, self.clut_y)
        return resolved


classes = (
    RCARDT_OT_ReloadPresets,
    RCARDT_ObjectSetting,
    RCARDT_MaterialSetting,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.rcardt_object = bpy.props.PointerProperty(
        type=RCARDT_ObjectSetting)
    bpy.types.Material.rcardt_material = bpy.props.PointerProperty(
        type=RCARDT_MaterialSetting)
    bpy.types.Scene.rcardt_clut_preset_file = bpy.props.StringProperty(
        name="CLUT Preset File",
        description="clut_presets.json describing this car's palette layout, "
                    "as written by 'C1CircuitTool rcardt-unpack'. Importing a "
                    "model fills this in automatically. Leave empty to use "
                    "the built-in slots",
        subtype='FILE_PATH',
        default="",
    )
    bpy.types.Scene.rcardt_trailing_bytes = bpy.props.StringProperty(
        name="Trailing Bytes",
        description="Hex of any bytes that followed the last surface in the "
                    "imported file. The retail SW20 ships 60 zero bytes "
                    "there; keeping them lets it export byte identically",
        default="",
    )


def unregister():
    del bpy.types.Scene.rcardt_trailing_bytes
    del bpy.types.Scene.rcardt_clut_preset_file
    del bpy.types.Object.rcardt_object
    del bpy.types.Material.rcardt_material
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
