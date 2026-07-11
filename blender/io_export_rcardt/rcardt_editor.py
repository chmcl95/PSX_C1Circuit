import bpy

MSG_HEX_2 = '{0}: 0x{1:02X}'
MSG_HEX_4 = '{0}: 0x{1:04X}'


# ---------------------------------------------------------------------------
# Object Editor: assigns an object to one of the 4 fixed RCARDT nodes
# ---------------------------------------------------------------------------
class OBJECT_PT_RCARDT_Object_Editor(bpy.types.Panel):
    bl_idname = "OBJECT_PT_RCARDT_Object_Editor"
    bl_label = "RCARDT Node Editor"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'MESH'

    def draw(self, context):
        obj = context.object
        settings = obj.rcardt_object
        layout = self.layout

        layout.prop(settings, "enabled")
        col = layout.column()
        col.enabled = settings.enabled
        col.prop(settings, "node_index")
        col.prop(settings, "auto_transform")

        sub = col.column()
        sub.enabled = not settings.auto_transform
        sub.prop(settings, "position")
        sub.prop(settings, "rotation")

        if settings.auto_transform:
            box = col.box()
            box.label(text="Auto-derived from Object Transform:")
            row = box.row()
            row.label(text=f"Location: "
                           f"({obj.location.x:.2f}, {obj.location.y:.2f}, "
                           f"{obj.location.z:.2f})")


# ---------------------------------------------------------------------------
# Material Editor: PS1 GPU polygon packet parameters
# ---------------------------------------------------------------------------
class OBJECT_PT_RCARDT_Material_Editor(bpy.types.Panel):
    bl_idname = "OBJECT_PT_RCARDT_Material_Editor"
    bl_label = "RCARDT Material Editor"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.active_material is not None

    def draw(self, context):
        mat = context.object.active_material
        settings = mat.rcardt_material
        layout = self.layout

        layout.prop(settings, "color")

        header = layout.row()
        header.prop(settings, "show_command", text="GPU Command Flags",
                    icon='TRIA_DOWN' if settings.show_command else 'TRIA_RIGHT',
                    emboss=False)
        if settings.show_command:
            box = layout.box()
            box.prop(settings, "textured")
            box.prop(settings, "raw_texture")
            box.prop(settings, "semi_transparent")
            box.prop(settings, "gouraud")

        header = layout.row()
        header.prop(settings, "show_clut", text="CLUT",
                    icon='TRIA_DOWN' if settings.show_clut else 'TRIA_RIGHT',
                    emboss=False)
        if settings.show_clut:
            box = layout.box()
            box.prop(settings, "clut_x")
            box.prop(settings, "clut_y")
            box.label(text=f"VRAM: ({settings.clut_x * 16}, {settings.clut_y})")

        header = layout.row()
        header.prop(settings, "show_texpage", text="Texture Page",
                    icon='TRIA_DOWN' if settings.show_texpage else 'TRIA_RIGHT',
                    emboss=False)
        if settings.show_texpage:
            box = layout.box()
            box.prop(settings, "texpage_x")
            box.prop(settings, "texpage_y")
            box.label(text=f"VRAM: ({settings.texpage_x * 64}, "
                           f"{settings.texpage_y * 256})")
            box.prop(settings, "semi_transparency_mode")
            box.prop(settings, "texture_page_colors")
            box.prop(settings, "texture_disable")

        header = layout.row()
        header.prop(settings, "show_advanced", text="Advanced / Unknown Fields",
                    icon='TRIA_DOWN' if settings.show_advanced else 'TRIA_RIGHT',
                    emboss=False)
        if settings.show_advanced:
            box = layout.box()
            box.prop(settings, "unk_bit9")
            box.prop(settings, "unk_bit12")
            box.prop(settings, "unknown_tail")


classes = (
    OBJECT_PT_RCARDT_Object_Editor,
    OBJECT_PT_RCARDT_Material_Editor,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
