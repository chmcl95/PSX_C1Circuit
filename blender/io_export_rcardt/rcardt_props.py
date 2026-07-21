import bpy


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
                    "(0-3). Typically 0 = body, 1-3 = wheels/sub-parts",
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
        description="Enable semi-transparency blending",
        default=False,
    )
    gouraud: bpy.props.BoolProperty(
        name="Gouraud Shading",
        description="Mark surface as Gouraud shaded (this format still "
                    "only stores a single flat color per surface)",
        default=False,
    )

    # --- CLUT (Color Lookup Table location in VRAM) ---
    clut_x: bpy.props.IntProperty(
        name="CLUT X (raw)",
        description="Raw CLUT X coordinate. Actual VRAM X = value * 16",
        default=0, min=0, max=63,
    )
    clut_y: bpy.props.IntProperty(
        name="CLUT Y",
        description="CLUT Y coordinate in VRAM (0-511)",
        default=0, min=0, max=511,
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
        default=False,
    )

    # --- Raw passthrough / unknown fields, exposed for advanced tweaking ---
    unk_bit9: bpy.props.IntProperty(
        name="Unknown Texpage bit9-10", default=0, min=0, max=3,
    )
    unk_bit12: bpy.props.IntProperty(
        name="Unknown Texpage bit12-15", default=0, min=0, max=15,
    )
    unknown_tail: bpy.props.IntVectorProperty(
        name="Unknown Tail (0x2C)",
        description="Raw passthrough for the 6 unknown shorts at the end "
                    "of every Surface",
        default=(0, 0, 0, 0, 0, 0), size=6, min=0, max=65535,
    )

    # UI collapsible section flags
    show_command: bpy.props.BoolProperty(default=True)
    show_clut: bpy.props.BoolProperty(default=False)
    show_texpage: bpy.props.BoolProperty(default=False)
    show_advanced: bpy.props.BoolProperty(default=False)


classes = (
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


def unregister():
    del bpy.types.Object.rcardt_object
    del bpy.types.Material.rcardt_material
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
