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
    int16   unknown[6]

All multi-byte fields are little endian (PS1 / MIPS).
"""

import struct

NODE_COUNT = 4
NODE_STRUCT_SIZE = 32
SURFACE_STRUCT_SIZE = 60

_NODE_FMT = '<i3i3iI'          # surfaceLength, position(3), rotation(3), ptr_mdl
_SURFACE_HEAD_FMT = '<3sBBBHBBHBBBB'
# color(3s) command(B) uv0.u(B) uv0.v(B) clut(H) uv1.u(B) uv1.v(B)
# texpage(H) uv2.u(B) uv2.v(B) uv3.u(B) uv3.v(B)


def clamp(value, lo, hi):
    return max(lo, min(hi, int(round(value))))


def clamp_short(value):
    return clamp(value, -32768, 32767)

def clamp_ushort(value):
    return clamp(value, 0, 65535)

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


class RcardtSurface:
    """One PS1 GPU polygon packet (quad or triangle-as-quad)."""

    __slots__ = (
        'color', 'raw_texture', 'semi_transparent', 'textured', 'is_quad',
        'gouraud', 'render_type',
        'uv0', 'uv1', 'uv2', 'uv3',
        'clut_x', 'clut_y',
        'texpage_x', 'texpage_y', 'semi_transparency', 'texture_page_colors',
        'unk_bit9', 'texture_disable', 'unk_bit12',
        'positions', 'unknown_tail',
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
        self.unknown_tail = (0, 0, 0, 0, 0, 0)

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
        tail = struct.pack('<6H', *[clamp_ushort(v) for v in self.unknown_tail])
        data = head + body + tail
        assert len(data) == SURFACE_STRUCT_SIZE, \
            f"Surface size mismatch: {len(data)} != {SURFACE_STRUCT_SIZE}"
        return data


class RcardtNode:
    """One of the 4 fixed model nodes (e.g. body / wheel parts)."""

    __slots__ = ('position', 'rotation', 'surfaces')

    def __init__(self):
        self.position = (0, 0, 0)
        self.rotation = (0, 0, 0)
        self.surfaces = []

    def pack_header(self):
        return struct.pack(
            _NODE_FMT,
            len(self.surfaces),
            int(self.position[0]), int(self.position[1]), int(self.position[2]),
            int(self.rotation[0]), int(self.rotation[1]), int(self.rotation[2]),
            0,  # ptr_mdl, runtime-only value
        )

    def pack_surfaces(self):
        return b''.join(s.pack() for s in self.surfaces)


class RcardtModel:
    """Full 00000000 model file: exactly 4 nodes."""

    def __init__(self):
        self.nodes = [RcardtNode() for _ in range(NODE_COUNT)]

    def pack(self):
        headers = b''.join(n.pack_header() for n in self.nodes)
        bodies = b''.join(n.pack_surfaces() for n in self.nodes)
        return headers + bodies

    def write(self, filepath):
        data = self.pack()
        with open(filepath, 'wb') as f:
            f.write(data)
        return data
