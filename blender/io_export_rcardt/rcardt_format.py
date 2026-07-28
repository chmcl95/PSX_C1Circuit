"""
RCARDT model (00000000) binary format.

Layout reverse engineered from c1circuit_rcardt_model.bt (010 Editor
Binary Template) and cross-checked against sample_RCARDT/*/00000000
sample files.

File layout::

    Node   nodes[4]                # 32 bytes each -> 128 bytes total
    Object object(nodes[0].surfaceLength)   # nodes[0].surfaceLength * 60 bytes
    Object object(nodes[1].surfaceLength)
    Object object(nodes[2].surfaceLength)
    Object object(nodes[3].surfaceLength)

Node (32 bytes, little endian)::

    int32   surfaceLength
    int32   position[3]
    int32   rotation[3]
    uint32  ptr_mdl        # runtime pointer, always written as 0

Surface (60 bytes, little endian)::

    uint8   color[3]
    uint8   command        # bitfield, see pack_command()
    uint8   uv0[2]
    uint16  clut           # bitfield, see pack_clut()
    uint8   uv1[2]
    uint16  texpage        # bitfield, see pack_texpage()
    uint8   uv2[2]
    uint8   uv3[2]
    int16   position[4][4] # 4 vertices * (x, y, z, padding)
    int32   normal[3]      # documented as "unknown[6]" until now

All multi-byte fields are little endian (PS1 / MIPS).

The trailing 12 bytes used to be read as 6 opaque uint16. They are three
int32 holding the surface's unnormalized face normal, equal to
``cross(v1 - v0, v2 - v0)`` over the *stored* vertex order. Verified byte
exact against every surface of the retail FD3S (242), NA8C (222) and SW20
(226) models, so this module derives them from the geometry instead of
carrying them as authorable data.
"""

import struct

NODE_COUNT = 4
NODE_STRUCT_SIZE = 32
SURFACE_STRUCT_SIZE = 60
HEADER_SIZE = NODE_COUNT * NODE_STRUCT_SIZE

_NODE_FMT = '<i3i3iI'          # surfaceLength, position(3), rotation(3), ptr_mdl
_SURFACE_HEAD_FMT = '<3sBBBHBBHBBBB'
# color(3s) command(B) uv0.u(B) uv0.v(B) clut(H) uv1.u(B) uv1.v(B)
# texpage(H) uv2.u(B) uv2.v(B) uv3.u(B) uv3.v(B)
_NORMAL_FMT = '<3i'


class RcardtFormatError(ValueError):
    """Raised when a file does not match the RCARDT model layout."""


def clamp(value, lo, hi):
    return max(lo, min(hi, int(round(value))))


def clamp_short(value):
    return clamp(value, -32768, 32767)

def clamp_long(value):
    return clamp(value, -2147483648, 2147483647)

def clamp_byte(value):
    return clamp(value, 0, 255)


# ---------------------------------------------------------------------------
# Bitfields
# ---------------------------------------------------------------------------

def pack_command(raw_texture, semi_transparent, textured, is_quad,
                  gouraud, render_type):
    """
    PSX_GPU_COMMAND (1 byte, bit0 = LSB, first declared field):
        bit0    raw_texture
        bit1    semi_transparent
        bit2    textured
        bit3    is_quad
        bit4    gouraud
        bit5-7  render_type (1: polygon, 2: line, 3: rectangle)
    """
    value = 0
    value |= (1 if raw_texture else 0) << 0
    value |= (1 if semi_transparent else 0) << 1
    value |= (1 if textured else 0) << 2
    value |= (1 if is_quad else 0) << 3
    value |= (1 if gouraud else 0) << 4
    value |= (render_type & 0x7) << 5
    return value & 0xFF


def unpack_command(value):
    return {
        'raw_texture': bool(value & 0x01),
        'semi_transparent': bool(value & 0x02),
        'textured': bool(value & 0x04),
        'is_quad': bool(value & 0x08),
        'gouraud': bool(value & 0x10),
        'render_type': (value >> 5) & 0x7,
    }


def pack_clut(clut_x, clut_y):
    """
    PSX_GPU_CLUT (2 bytes / ushort):
        bit0-5  x_coordinate (needs *16 for actual VRAM X)
        bit6-14 y_coordinate (immediate VRAM Y)
        bit15   unused (pad : 0 width)
    """
    value = 0
    value |= (clut_x & 0x3F) << 0
    value |= (clut_y & 0x1FF) << 6
    return value & 0xFFFF


def unpack_clut(value):
    return {
        'clut_x': value & 0x3F,
        'clut_y': (value >> 6) & 0x1FF,
    }


def pack_texpage(texpage_x, texpage_y, semi_transparency, texture_page_colors,
                 unk_bit9=0, texture_disable=False, unk_bit12=0):
    """
    PSX_GPU_Texpage (2 bytes / ushort):
        bit0-3   texpage_x (needs *64 for actual VRAM X)
        bit4     texpage_y (needs *256 for actual VRAM Y)
        bit5-6   semi_transparency mode
        bit7-8   texture_page_colors (0:4bit 1:8bit 2:15bit 3:reserved)
        bit9-10  unk_bit9
        bit11    texture_disable
        bit12-15 unk_bit12
    """
    value = 0
    value |= (texpage_x & 0xF) << 0
    value |= (texpage_y & 0x1) << 4
    value |= (semi_transparency & 0x3) << 5
    value |= (texture_page_colors & 0x3) << 7
    value |= (unk_bit9 & 0x3) << 9
    value |= (1 if texture_disable else 0) << 11
    value |= (unk_bit12 & 0xF) << 12
    return value & 0xFFFF


def unpack_texpage(value):
    return {
        'texpage_x': value & 0xF,
        'texpage_y': (value >> 4) & 0x1,
        'semi_transparency': (value >> 5) & 0x3,
        'texture_page_colors': (value >> 7) & 0x3,
        'unk_bit9': (value >> 9) & 0x3,
        'texture_disable': bool((value >> 11) & 0x1),
        'unk_bit12': (value >> 12) & 0xF,
    }


def face_normal(positions):
    """The last 12 bytes of a Surface: its unnormalized face normal.

    ``cross(v1 - v0, v2 - v0)`` over the four stored vertices in the order
    they are written to the file. Degenerate faces yield (0, 0, 0), which
    also occurs in retail data.
    """
    v0, v1, v2 = positions[0], positions[1], positions[2]
    ax, ay, az = v1.x - v0.x, v1.y - v0.y, v1.z - v0.z
    bx, by, bz = v2.x - v0.x, v2.y - v0.y, v2.z - v0.z
    return (
        clamp_long(ay * bz - az * by),
        clamp_long(az * bx - ax * bz),
        clamp_long(ax * by - ay * bx),
    )


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class RcardtVertex:
    __slots__ = ('x', 'y', 'z')

    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z

    def pack(self):
        return struct.pack('<4h', clamp_short(self.x), clamp_short(self.y),
                            clamp_short(self.z), 0)

    def as_tuple(self):
        return (self.x, self.y, self.z)


class RcardtSurface:
    """One PS1 GPU polygon packet (quad or triangle-as-quad)."""

    __slots__ = (
        'color', 'raw_texture', 'semi_transparent', 'textured', 'is_quad',
        'gouraud', 'render_type',
        'uv0', 'uv1', 'uv2', 'uv3',
        'clut_x', 'clut_y',
        'texpage_x', 'texpage_y', 'semi_transparency', 'texture_page_colors',
        'unk_bit9', 'texture_disable', 'unk_bit12',
        'positions', 'stored_normal',
    )

    def __init__(self):
        self.color = (128, 128, 128)
        self.raw_texture = False
        self.semi_transparent = False
        self.textured = True
        self.is_quad = True
        self.gouraud = False
        self.render_type = 1  # polygon

        self.uv0 = (0, 0)
        self.uv1 = (0, 0)
        self.uv2 = (0, 0)
        self.uv3 = (0, 0)

        self.clut_x = 0
        self.clut_y = 0

        self.texpage_x = 0
        self.texpage_y = 0
        self.semi_transparency = 0
        self.texture_page_colors = 0
        self.unk_bit9 = 0
        self.texture_disable = False
        self.unk_bit12 = 0

        self.positions = [RcardtVertex(), RcardtVertex(),
                           RcardtVertex(), RcardtVertex()]
        # What the file we were read from actually held. Reporting only; the
        # value written back out is always recomputed from the geometry.
        self.stored_normal = None

    @property
    def normal(self):
        return face_normal(self.positions)

    def pack(self):
        command = pack_command(
            self.raw_texture, self.semi_transparent, self.textured,
            self.is_quad, self.gouraud, self.render_type)
        clut = pack_clut(self.clut_x, self.clut_y)
        texpage = pack_texpage(
            self.texpage_x, self.texpage_y, self.semi_transparency,
            self.texture_page_colors, self.unk_bit9, self.texture_disable,
            self.unk_bit12)

        color_bytes = bytes((clamp_byte(self.color[0]),
                              clamp_byte(self.color[1]),
                              clamp_byte(self.color[2])))

        head = struct.pack(
            _SURFACE_HEAD_FMT,
            color_bytes,
            command,
            clamp_byte(self.uv0[0]), clamp_byte(self.uv0[1]),
            clut,
            clamp_byte(self.uv1[0]), clamp_byte(self.uv1[1]),
            texpage,
            clamp_byte(self.uv2[0]), clamp_byte(self.uv2[1]),
            clamp_byte(self.uv3[0]), clamp_byte(self.uv3[1]),
        )
        body = b''.join(v.pack() for v in self.positions)
        tail = struct.pack(_NORMAL_FMT, *self.normal)
        data = head + body + tail
        assert len(data) == SURFACE_STRUCT_SIZE, \
            f"Surface size mismatch: {len(data)} != {SURFACE_STRUCT_SIZE}"
        return data

    @classmethod
    def unpack_from(cls, data, offset):
        surf = cls()
        (color, command, u0, v0, clut, u1, v1, texpage,
         u2, v2, u3, v3) = struct.unpack_from(_SURFACE_HEAD_FMT, data, offset)

        surf.color = tuple(color)
        for key, value in unpack_command(command).items():
            setattr(surf, key, value)
        for key, value in unpack_clut(clut).items():
            setattr(surf, key, value)
        for key, value in unpack_texpage(texpage).items():
            setattr(surf, key, value)

        surf.uv0, surf.uv1, surf.uv2, surf.uv3 = \
            (u0, v0), (u1, v1), (u2, v2), (u3, v3)

        surf.positions = []
        for i in range(4):
            x, y, z, _pad = struct.unpack_from('<4h', data, offset + 0x10 + i * 8)
            surf.positions.append(RcardtVertex(x, y, z))

        surf.stored_normal = struct.unpack_from(_NORMAL_FMT, data, offset + 0x30)
        return surf

    def normal_is_stale(self):
        """True when the file's normal disagrees with its own geometry.

        Retail RCARDT models never do. Models converted from the menu
        (ALLCAR) format do, because their vertices were rescaled without
        recomputing the normals.
        """
        return (self.stored_normal is not None
                and tuple(self.stored_normal) != self.normal)

    def material_key(self):
        """Everything that belongs to a material rather than to a face.

        ``is_quad``, the vertices, the UVs and the normal are per-face and
        excluded, which is what collapses a 242 surface model into 4
        materials instead of 216.
        """
        return (
            tuple(self.color),
            self.raw_texture, self.semi_transparent, self.textured,
            self.gouraud, self.render_type,
            self.clut_x, self.clut_y,
            self.texpage_x, self.texpage_y, self.semi_transparency,
            self.texture_page_colors, self.unk_bit9, self.texture_disable,
            self.unk_bit12,
        )


class RcardtNode:
    """One of the 4 fixed model nodes (body / front wheels / rear wheels)."""

    __slots__ = ('position', 'rotation', 'surfaces', 'ptr_mdl')

    def __init__(self):
        self.position = (0, 0, 0)
        self.rotation = (0, 0, 0)
        self.surfaces = []
        # Runtime-only pointer. Retail files hold a leftover PSX RAM address
        # that the loader overwrites, so a fresh export writes 0. Import
        # keeps the original so re-exporting reproduces the file exactly.
        self.ptr_mdl = 0

    def pack_header(self):
        return struct.pack(
            _NODE_FMT,
            len(self.surfaces),
            int(self.position[0]), int(self.position[1]), int(self.position[2]),
            int(self.rotation[0]), int(self.rotation[1]), int(self.rotation[2]),
            int(self.ptr_mdl) & 0xFFFFFFFF,
        )

    def pack_surfaces(self):
        return b''.join(s.pack() for s in self.surfaces)


class RcardtModel:
    """Full 00000000 model file: exactly 4 nodes."""

    def __init__(self):
        self.nodes = [RcardtNode() for _ in range(NODE_COUNT)]
        # Bytes past the last surface. The retail SW20 ships 60 zero bytes of
        # padding; keeping them lets that file round-trip byte for byte.
        self.trailing = b''

    def pack(self):
        headers = b''.join(n.pack_header() for n in self.nodes)
        bodies = b''.join(n.pack_surfaces() for n in self.nodes)
        return headers + bodies + self.trailing

    def write(self, filepath):
        data = self.pack()
        with open(filepath, 'wb') as f:
            f.write(data)
        return data

    # -- reading ---------------------------------------------------------
    @classmethod
    def unpack(cls, data):
        if len(data) < HEADER_SIZE:
            raise RcardtFormatError(
                f"File is {len(data)} bytes, too short for the 128 byte node "
                f"header block.")

        model = cls()
        counts = []
        for i in range(NODE_COUNT):
            (count, px, py, pz, rx, ry, rz, ptr) = struct.unpack_from(
                _NODE_FMT, data, i * NODE_STRUCT_SIZE)
            if count < 0:
                raise RcardtFormatError(_diagnose(data, i, count))
            counts.append(count)
            model.nodes[i].position = (px, py, pz)
            model.nodes[i].rotation = (rx, ry, rz)
            model.nodes[i].ptr_mdl = ptr

        expected = HEADER_SIZE + sum(counts) * SURFACE_STRUCT_SIZE
        if expected > len(data):
            raise RcardtFormatError(_diagnose(data, None, sum(counts)))

        offset = HEADER_SIZE
        for i in range(NODE_COUNT):
            for _ in range(counts[i]):
                model.nodes[i].surfaces.append(
                    RcardtSurface.unpack_from(data, offset))
                offset += SURFACE_STRUCT_SIZE

        model.trailing = data[offset:]
        return model

    @classmethod
    def read(cls, filepath):
        with open(filepath, 'rb') as f:
            return cls.unpack(f.read())


def looks_like_menu_model(data):
    """True for the ALLCAR (menu) layout: uint32 count + surfaces.

    The menu format is the race format minus 124 bytes: it keeps only the
    first surfaceLength field and drops the rest of the node header block.
    The retail HK11 (the cut March) ships in RCARDT with this layout, which
    is why the game cannot load it.
    """
    if len(data) < 4:
        return False
    count = struct.unpack_from('<I', data, 0)[0]
    return count > 0 and 4 + count * SURFACE_STRUCT_SIZE == len(data)


def _diagnose(data, node_index, count):
    if looks_like_menu_model(data):
        total = struct.unpack_from('<I', data, 0)[0]
        return (f"This file has the ALLCAR (menu) layout: a single surface "
                f"count of {total} followed by {total} surfaces, with the "
                f"remaining 124 bytes of the node header missing. The race "
                f"format needs a full 128 byte, 4 node header. Add the "
                f"missing 124 bytes and split the surfaces across the 4 "
                f"nodes before importing.")
    if node_index is not None:
        return (f"Node {node_index}: negative surfaceLength ({count}). This is "
                f"not an RCARDT 00000000 model file.")
    return (f"The node headers declare {count} surfaces "
            f"({HEADER_SIZE + count * SURFACE_STRUCT_SIZE} bytes) but the file "
            f"is only {len(data)} bytes. This is not an RCARDT 00000000 model "
            f"file.")
