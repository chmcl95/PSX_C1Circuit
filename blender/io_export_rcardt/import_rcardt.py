"""
Import an existing RCARDT model (00000000.BIN) back into Blender.

Every conversion here is the exact inverse of the matching step in
export_rcardt, so importing a retail file and exporting it again with the
same options reproduces the original bytes.

Material de-duplication is what the face-normal work bought us: the 12
trailing bytes of a surface are per-face data, not material data, so keying
materials on the GPU state alone collapses a 242 surface model into 4
materials instead of the 216 you get when the normal is treated as part of
the material.
"""

import math
import os

import bpy
import mathutils
from bpy.props import BoolProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from . import rcardt_presets
from .export_rcardt import AXIS_ROTATION_MATRIX
from .rcardt_format import NODE_COUNT, RcardtFormatError, RcardtModel
from .rcardt_props import preset_file_path

NODE_NAMES = ("body", "wheel_front_a", "wheel_front_b", "wheel_rear")

MSG_DONE = "RCARDT import: {0} object(s), {1} surface(s), {2} material(s)."
MSG_STALE_NORMALS = ("{0} surface(s) carry a face normal that does not match "
                     "their own geometry. Exporting recomputes them, so the "
                     "file will not come back byte identical.")
MSG_TRIANGLES = ("{0} surface(s) are triangles. The game only draws quads "
                 "correctly, so this model may already render wrong.")
MSG_PRESETS = "CLUT slots loaded from {0}."
MSG_NO_PRESETS = ("No clut_presets.json next to the model, so materials use "
                  "raw CLUT coordinates. Run 'C1CircuitTool rcardt-unpack' to "
                  "generate one.")
MSG_TRAILING = ("{0} trailing byte(s) after the last surface were kept as-is "
                "and will be written back on export.")

INV_AXIS_ROTATION_MATRIX = AXIS_ROTATION_MATRIX.inverted()


def _psx_units_to_angle(units):
    """Inverse of export_rcardt._angle_to_psx_units."""
    return (units % 4096) * 2.0 * math.pi / 4096.0


def _byte_to_uv(uv, flip_v):
    u = uv[0] / 255.0
    v = 1.0 - (uv[1] / 255.0) if flip_v else uv[1] / 255.0
    return (u, v)


def _file_order_to_loop_order(count, options):
    """File vertex slots, listed in Blender face-loop order.

    Export builds the stored order as::

        quad: loops -> [0,1,3,2] (reorder_quad) -> swap slots 1 and 2 (flip_winding)
        tri : loops -> [0,1,2,2]                -> swap slots 1 and 2 (flip_winding)

    so this returns the permutation that undoes both steps.
    """
    if count == 4:
        stored = [0, 1, 3, 2] if options['reorder_quad'] else [0, 1, 2, 3]
    else:
        stored = [0, 1, 2, 2]   # triangle: the 4th slot repeats the 3rd loop
    if options['flip_winding']:
        stored = [stored[0], stored[2], stored[1], stored[3]]
    # stored[i] is the loop that ended up in file slot i, so invert it. A
    # triangle's repeated loop appears twice and the first slot wins.
    return [stored.index(loop) for loop in range(count)]


def _make_material(name, surf, table, use_presets):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    settings = mat.rcardt_material

    settings.color = tuple(surf.color)
    settings.raw_texture = surf.raw_texture
    settings.semi_transparent = surf.semi_transparent
    settings.textured = surf.textured
    settings.gouraud = surf.gouraud
    settings.render_type = surf.render_type

    settings.clut_x = surf.clut_x
    settings.clut_y = surf.clut_y
    slot = table.match(surf.clut_x, surf.clut_y) if use_presets else None
    settings.clut_preset = slot or rcardt_presets.MANUAL_ID

    settings.texpage_x = surf.texpage_x
    settings.texpage_y = surf.texpage_y
    settings.semi_transparency_mode = str(surf.semi_transparency)
    settings.texture_page_colors = str(surf.texture_page_colors)
    settings.texture_disable = surf.texture_disable
    settings.unk_bit9 = surf.unk_bit9
    settings.unk_bit12 = surf.unk_bit12

    # Give the viewport something recognisable to show.
    rgb = tuple(c / 255.0 for c in surf.color)
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled is not None:
        principled.inputs["Base Color"].default_value = (*rgb, 1.0)
    mat.diffuse_color = (*rgb, 1.0)
    return mat


def _material_name(base, surf, index, table, use_presets):
    slot = table.match(surf.clut_x, surf.clut_y) if use_presets else None
    parts = [base, f"{index:02d}", slot or f"clut{surf.clut_y}"]
    if not surf.textured or surf.texture_disable:
        parts.append("untex")
    if surf.semi_transparent:
        parts.append("semi")
    return "_".join(parts)


def _build_node_object(node_index, node, options, table, base_name, counters,
                       shared_materials):
    """Create one Blender mesh object for a node. Returns (object, materials).

    *shared_materials* maps a surface's material key to a Blender material and
    is carried across all 4 nodes, so a body and a wheel drawing with the same
    GPU state share one material instead of getting a copy each.
    """
    scale = options['position_scale']
    name = f"{base_name}_{node_index}_{NODE_NAMES[node_index]}"

    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)

    verts = []
    faces = []
    face_uvs = []
    face_material = []

    materials = []
    slot_by_key = {}

    for surf in node.surfaces:
        key = surf.material_key()
        mat_index = slot_by_key.get(key)
        if mat_index is None:
            mat = shared_materials.get(key)
            if mat is None:
                mat = _make_material(
                    _material_name(base_name, surf, len(shared_materials), table,
                                   options['use_clut_presets']),
                    surf, table, options['use_clut_presets'])
                shared_materials[key] = mat
            mat_index = len(materials)
            slot_by_key[key] = mat_index
            materials.append(mat)
        face_material.append(mat_index)

        count = 4 if surf.is_quad else 3
        if not surf.is_quad:
            counters['triangles'] += 1
        if surf.normal_is_stale():
            counters['stale_normals'] += 1

        order = _file_order_to_loop_order(count, options)
        base = len(verts)
        loop_uvs = []
        for file_slot in order:
            v = surf.positions[file_slot]
            co = INV_AXIS_ROTATION_MATRIX @ mathutils.Vector(
                (v.x / scale, v.y / scale, v.z / scale))
            verts.append(co)
            uv = (surf.uv0, surf.uv1, surf.uv2, surf.uv3)[file_slot]
            loop_uvs.append(_byte_to_uv(uv, options['flip_v']))
        faces.append(tuple(range(base, base + count)))
        face_uvs.append(loop_uvs)

    mesh.from_pydata(verts, [], faces)
    for mat in materials:
        mesh.materials.append(mat)

    uv_layer = mesh.uv_layers.new(name="UVMap")
    for poly, uvs, mat_index in zip(mesh.polygons, face_uvs, face_material):
        poly.material_index = mat_index
        for loop_index, uv in zip(poly.loop_indices, uvs):
            uv_layer.data[loop_index].uv = uv

    if options['merge_vertices']:
        _merge_by_distance(mesh, options['merge_distance'])

    mesh.update()
    mesh.validate()

    settings = obj.rcardt_object
    settings.enabled = True
    settings.node_index = node_index
    settings.auto_transform = True
    settings.ptr_mdl = node.ptr_mdl
    settings.position = tuple(node.position)
    settings.rotation = tuple(node.rotation)

    obj.location = INV_AXIS_ROTATION_MATRIX @ mathutils.Vector(
        (node.position[0] / scale, node.position[1] / scale,
         node.position[2] / scale))
    obj.rotation_euler = tuple(_psx_units_to_angle(r) for r in node.rotation)

    return obj, materials


def _merge_by_distance(mesh, distance):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=distance)
    bm.to_mesh(mesh)
    bm.free()


def import_model(context, filepath, options):
    """Read *filepath* and build the node objects. Returns (objects, warnings)."""
    warnings = []
    model = RcardtModel.read(filepath)

    preset_path = rcardt_presets.sibling_preset_file(filepath)
    if preset_path and options['use_clut_presets']:
        context.scene.rcardt_clut_preset_file = preset_path
        rcardt_presets.invalidate_cache()
        warnings.append(MSG_PRESETS.format(preset_path))
    elif options['use_clut_presets']:
        warnings.append(MSG_NO_PRESETS)
    table = rcardt_presets.get_table(preset_file_path(context))

    base_name = os.path.basename(os.path.dirname(filepath)) or "RCARDT"
    counters = {'triangles': 0, 'stale_normals': 0}

    objects = []
    total_surfaces = 0
    shared_materials = {}
    for i in range(NODE_COUNT):
        node = model.nodes[i]
        if not node.surfaces and options['skip_empty_nodes']:
            continue
        obj, _materials = _build_node_object(
            i, node, options, table, base_name, counters, shared_materials)
        objects.append(obj)
        total_surfaces += len(node.surfaces)
    total_materials = len(shared_materials)

    if counters['triangles']:
        warnings.append(MSG_TRIANGLES.format(counters['triangles']))
    if counters['stale_normals']:
        warnings.append(MSG_STALE_NORMALS.format(counters['stale_normals']))
    context.scene.rcardt_trailing_bytes = model.trailing.hex()
    if model.trailing:
        warnings.append(MSG_TRAILING.format(len(model.trailing)))

    warnings.append(MSG_DONE.format(len(objects), total_surfaces,
                                    total_materials))
    return objects, warnings


class IMPORT_OT_RCARDT(bpy.types.Operator, ImportHelper):
    """Import an RCARDT car model file (00000000)"""

    bl_idname = "import_scene.rcardt"
    bl_label = "Import RCARDT Model"
    bl_description = "Import a PS1 RCARDT car model (00000000)"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".BIN"
    filter_glob: StringProperty(default="*.BIN;*", options={'HIDDEN'})

    position_scale: FloatProperty(
        name="Position Scale",
        description="Divisor applied to the file's integer coordinates. Must "
                    "match the value used on export",
        default=100.0, min=0.0001,
    )
    reorder_quad: BoolProperty(
        name="Reorder Quad Vertices (Strip -> Fan)",
        description="Undo the PS1 triangle-strip vertex order. Must match "
                    "the export option",
        default=True,
    )
    flip_winding: BoolProperty(
        name="Flip Winding (Front/Back Facing)",
        description="Undo the export-side winding flip. Must match the "
                    "export option",
        default=True,
    )
    flip_v: BoolProperty(
        name="Flip UV V",
        description="Undo the export-side V flip. Must match the export option",
        default=True,
    )
    use_clut_presets: BoolProperty(
        name="Use CLUT Slots",
        description="Load the clut_presets.json sitting next to the model and "
                    "map each material's palette onto a named slot. Materials "
                    "whose palette is not in the file stay on raw coordinates",
        default=True,
    )
    merge_vertices: BoolProperty(
        name="Merge Vertices By Distance",
        description="Weld the duplicated corner vertices into an editable "
                    "mesh. Leave off for the most literal import, where every "
                    "surface stays a loose quad",
        default=False,
    )
    merge_distance: FloatProperty(
        name="Merge Distance",
        default=0.0001, min=0.0,
    )
    skip_empty_nodes: BoolProperty(
        name="Skip Empty Nodes",
        description="Do not create objects for nodes that hold no surfaces",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "position_scale")
        layout.prop(self, "reorder_quad")
        layout.prop(self, "flip_winding")
        layout.prop(self, "flip_v")
        layout.separator()
        layout.prop(self, "use_clut_presets")
        layout.prop(self, "skip_empty_nodes")
        layout.separator()
        layout.prop(self, "merge_vertices")
        sub = layout.row()
        sub.enabled = self.merge_vertices
        sub.prop(self, "merge_distance")

    def execute(self, context):
        options = {
            'position_scale': self.position_scale,
            'reorder_quad': self.reorder_quad,
            'flip_winding': self.flip_winding,
            'flip_v': self.flip_v,
            'use_clut_presets': self.use_clut_presets,
            'merge_vertices': self.merge_vertices,
            'merge_distance': self.merge_distance,
            'skip_empty_nodes': self.skip_empty_nodes,
        }
        try:
            _objects, warnings = import_model(context, self.filepath, options)
        except RcardtFormatError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Unexpected error: {e}")
            return {'CANCELLED'}

        for w in warnings:
            self.report({'INFO'}, w)
        return {'FINISHED'}


def menu_func_import(self, context):
    self.layout.operator(IMPORT_OT_RCARDT.bl_idname,
                         text="RCARDT Model (00000000)")


classes = (
    IMPORT_OT_RCARDT,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
