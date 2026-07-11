import math

import bmesh
import bpy
import mathutils
from bpy.props import BoolProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from .rcardt_format import RcardtModel, RcardtSurface, RcardtVertex, NODE_COUNT

MSG_WARN_NO_NODES = "No object has 'Include in RCARDT Export' enabled. " \
                    "An empty (all zero) file was written."
MSG_WARN_NODE_EMPTY = "Node {0}: no object assigned, writing an empty node " \
                      "(surfaceLength = 0)."
MSG_WARN_NODE_MULTI = "Node {0}: multiple objects assigned ({1}). " \
                      "Their geometry will be merged into a single node."
MSG_WARN_NGON = "Object '{0}': {1} n-gon face(s) triangulated automatically."
MSG_INFO_DONE = "RCARDT export finished: {0} node(s), {1} surface(s) total."

# Fixed +90 deg rotation around X, applied to both vertex positions and
# node header positions. Confirmed empirically to make the in-game
# orientation match the Blender scene.
AXIS_ROTATION_MATRIX = mathutils.Matrix.Rotation(math.radians(90), 4, (1.0, 0.0, 0.0))


def _angle_to_psx_units(radians_value):
    """Convert a Blender radian angle to a 12-bit PSX angle unit (0-4095)."""
    units = round(radians_value * 4096.0 / (2.0 * math.pi))
    return int(units) % 4096


def _gather_node_objects(context, use_selected_only):
    """Return dict: node_index -> list[Object], honoring rcardt_object.enabled."""
    source = context.selected_objects if use_selected_only else context.scene.objects
    buckets = {i: [] for i in range(NODE_COUNT)}
    for obj in source:
        if obj.type != 'MESH':
            continue
        settings = obj.rcardt_object
        if not settings.enabled:
            continue
        idx = max(0, min(NODE_COUNT - 1, settings.node_index))
        buckets[idx].append(obj)
    return buckets


def _material_settings_for(obj, material_index):
    """Return the RCARDT_MaterialSetting for a face's material, or None."""
    if material_index < len(obj.material_slots):
        mat = obj.material_slots[material_index].material
        if mat is not None:
            return mat.rcardt_material
    return None


def _build_surface(face_verts, mat_settings, uv_layer, options):
    """Build a single RcardtSurface from a bmesh face's (already ordered)
    list of BMVert-like (x, y, z) tuples plus per-vertex UV loops."""
    surf = RcardtSurface()

    if mat_settings is not None:
        surf.color = tuple(mat_settings.color)
        surf.raw_texture = mat_settings.raw_texture
        surf.semi_transparent = mat_settings.semi_transparent
        surf.textured = mat_settings.textured
        surf.gouraud = mat_settings.gouraud
        surf.clut_x = mat_settings.clut_x
        surf.clut_y = mat_settings.clut_y
        surf.texpage_x = mat_settings.texpage_x
        surf.texpage_y = mat_settings.texpage_y
        surf.semi_transparency = int(mat_settings.semi_transparency_mode)
        surf.texture_page_colors = int(mat_settings.texture_page_colors)
        surf.texture_disable = mat_settings.texture_disable
        surf.unk_bit9 = mat_settings.unk_bit9
        surf.unk_bit12 = mat_settings.unk_bit12
        surf.unknown_tail = tuple(mat_settings.unknown_tail)
    # else: keep RcardtSurface defaults

    return surf


def _uv_to_byte(uv, flip_v):
    u = round(uv[0] * 255.0)
    v = round((1.0 - uv[1]) * 255.0) if flip_v else round(uv[1] * 255.0)
    return (max(0, min(255, int(u))), max(0, min(255, int(v))))


def _export_object_surfaces(obj, options, warnings):
    """Triangulate/quadrangulate obj's mesh and return a list of
    RcardtSurface built from its local-space geometry."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_eval = obj.evaluated_get(depsgraph)
    mesh = obj_eval.to_mesh()

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    ngon_count = sum(1 for f in bm.faces if len(f.verts) > 4)
    if ngon_count > 0 and options['auto_triangulate']:
        ngon_faces = [f for f in bm.faces if len(f.verts) > 4]
        bmesh.ops.triangulate(bm, faces=ngon_faces, quad_method='BEAUTY',
                              ngon_method='BEAUTY')
        warnings.append(MSG_WARN_NGON.format(obj.name, ngon_count))

    uv_layer = bm.loops.layers.uv.active

    # Always rotate geometry +90 deg around X. This was confirmed to make
    # the in-game orientation match Blender's.
    bmesh.ops.rotate(bm, cent=(0.0, 0.0, 0.0), matrix=AXIS_ROTATION_MATRIX,
                     verts=bm.verts)

    scale = options['position_scale']
    surfaces = []

    for face in bm.faces:
        loops = list(face.loops)
        if len(loops) not in (3, 4):
            continue  # already triangulated above; skip stray n-gons

        mat_settings = _material_settings_for(obj, face.material_index)
        surf = _build_surface(None, mat_settings, uv_layer, options)
        surf.is_quad = (len(loops) == 4)

        if len(loops) == 4:
            # Blender fan order (0,1,2,3) -> PS1 GPU strip order (0,1,3,2)
            if options['reorder_quad']:
                ordered = [loops[0], loops[1], loops[3], loops[2]]
            else:
                ordered = loops
        else:
            # Triangle: duplicate the last vertex to fill the 4-slot packet
            ordered = [loops[0], loops[1], loops[2], loops[2]]

        # Swapping slots 1 and 2 reverses the winding of both triangles in
        # the packet without changing which diagonal splits the quad, i.e.
        # it flips front/back-facing for every surface uniformly. Exposed
        # as a toggle instead of requiring a manual code edit.
        if options['flip_winding']:
            ordered = [ordered[0], ordered[2], ordered[1], ordered[3]]

        positions = []
        uvs = []
        for loop in ordered:
            co = loop.vert.co
            positions.append(RcardtVertex(co.x * scale, co.y * scale, co.z * scale))
            if uv_layer is not None:
                uvs.append(_uv_to_byte(loop[uv_layer].uv, options['flip_v']))
            else:
                uvs.append((0, 0))

        surf.positions = positions
        surf.uv0, surf.uv1, surf.uv2, surf.uv3 = uvs
        surfaces.append(surf)

    bm.free()
    obj_eval.to_mesh_clear()
    return surfaces


def _build_node(node_index, objs, options, warnings):
    from .rcardt_format import RcardtNode
    node = RcardtNode()

    if not objs:
        warnings.append(MSG_WARN_NODE_EMPTY.format(node_index))
        return node

    if len(objs) > 1:
        warnings.append(MSG_WARN_NODE_MULTI.format(
            node_index, ", ".join(o.name for o in objs)))

    ref_obj = objs[0]
    settings = ref_obj.rcardt_object
    scale = options['position_scale']

    if settings.auto_transform:
        loc = AXIS_ROTATION_MATRIX @ ref_obj.location
        node.position = (
            round(loc.x * scale), round(loc.y * scale), round(loc.z * scale))
        eul = ref_obj.rotation_euler
        node.rotation = (
            _angle_to_psx_units(eul.x), _angle_to_psx_units(eul.y),
            _angle_to_psx_units(eul.z))
    else:
        pos = AXIS_ROTATION_MATRIX @ mathutils.Vector(settings.position)
        node.position = (round(pos.x), round(pos.y), round(pos.z))
        node.rotation = tuple(settings.rotation)

    for obj in objs:
        node.surfaces.extend(_export_object_surfaces(obj, options, warnings))

    return node


def build_model(context, options):
    """Build an RcardtModel from the current scene according to *options*.
    Returns (model, warnings)."""
    warnings = []
    buckets = _gather_node_objects(context, options['use_selected_only'])

    if all(len(v) == 0 for v in buckets.values()):
        warnings.append(MSG_WARN_NO_NODES)

    model = RcardtModel()
    for i in range(NODE_COUNT):
        model.nodes[i] = _build_node(i, buckets[i], options, warnings)

    total_surfaces = sum(len(n.surfaces) for n in model.nodes)
    warnings.append(MSG_INFO_DONE.format(NODE_COUNT, total_surfaces))
    return model, warnings


class EXPORT_OT_RCARDT(bpy.types.Operator, ExportHelper):
    """Export the scene's tagged node objects to an RCARDT model file
    (00000000)."""

    bl_idname = "export_scene.rcardt"
    bl_label = "Export RCARDT Model"
    bl_description = "Export a PS1 RCARDT car model (00000000)"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ""
    filter_glob: StringProperty(default="*", options={'HIDDEN'})

    use_selected_only: BoolProperty(
        name="Selected Objects Only",
        description="Only consider currently selected objects; otherwise "
                    "every object in the scene is checked",
        default=False,
    )
    position_scale: FloatProperty(
        name="Position Scale",
        description="Multiplier applied to Blender coordinates before "
                    "converting to the format's fixed-point integers. "
                    "Default 100 assumes 1 Blender unit = 1 meter and the "
                    "game uses centimeters",
        default=100.0, min=0.0001,
    )
    reorder_quad: BoolProperty(
        name="Reorder Quad Vertices (Fan -> Strip)",
        description="Reorder each quad's 4 vertices from Blender's fan "
                    "order to the PS1 GPU's triangle-strip order "
                    "(0,1,2,3) -> (0,1,3,2). This only changes which "
                    "diagonal splits the quad, not front/back facing. "
                    "Disable if geometry renders incorrectly in-game",
        default=True,
    )
    flip_winding: BoolProperty(
        name="Flip Winding (Front/Back Facing)",
        description="Reverse the winding order of every generated "
                    "triangle, flipping which side is considered the "
                    "front face in-game. Enable this if all faces appear "
                    "backwards/culled after exporting",
        default=False,
    )
    flip_v: BoolProperty(
        name="Flip UV V",
        description="Flip the V texture coordinate (top-down VRAM "
                    "convention)",
        default=True,
    )
    auto_triangulate: BoolProperty(
        name="Auto-Triangulate N-gons",
        description="Automatically triangulate faces with more than 4 "
                    "vertices (the format only supports triangles and "
                    "quads)",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "use_selected_only")
        layout.separator()
        layout.prop(self, "position_scale")
        layout.prop(self, "reorder_quad")
        layout.prop(self, "flip_winding")
        layout.prop(self, "flip_v")
        layout.prop(self, "auto_triangulate")

    def execute(self, context):
        options = {
            'use_selected_only': self.use_selected_only,
            'position_scale': self.position_scale,
            'reorder_quad': self.reorder_quad,
            'flip_winding': self.flip_winding,
            'flip_v': self.flip_v,
            'auto_triangulate': self.auto_triangulate,
        }
        try:
            model, warnings = build_model(context, options)
            model.write(self.filepath)
        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error: {e}")
            return {'CANCELLED'}

        for w in warnings:
            self.report({'INFO'}, w)
        return {'FINISHED'}


def menu_func_export(self, context):
    self.layout.operator(EXPORT_OT_RCARDT.bl_idname,
                         text="RCARDT Model (00000000)")


classes = (
    EXPORT_OT_RCARDT,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
