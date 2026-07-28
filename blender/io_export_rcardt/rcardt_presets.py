"""
CLUT slot presets, shared with C1CircuitTool.

A slot is a named palette position in VRAM. The same slot has to be written
twice with two different numbers -- once into the model (00000000.BIN, whose
CLUT X field stores VRAM_X / 16) and once into the texture (00000001.BIN,
whose CLUT block stores VRAM_X directly). Naming the slot once and letting
each side derive its own encoding is the entire point of this module.

``C1CircuitTool rcardt-unpack`` writes a ``clut_presets.json`` next to the
car's ``00000000.BIN`` describing that car's actual palette layout, and
``rcardt-pack`` reads it back. Importing the model here picks up the same
file, so the slot list in Blender always matches the car being modded.

With no preset file loaded, the built-in slots below apply. They cover the
palette rows whose purpose is known from the retail data.

This module deliberately has no ``bpy`` import so it can be tested with
plain CPython.
"""

import json
import os

JSON_FILENAME = "clut_presets.json"

MANUAL_ID = "__MANUAL__"
MANUAL_LABEL = "Manual (raw X/Y)"

DEFAULT_CLUT_VRAM_X = 128
# (name, clut_y, description). Confirmed against the retail RCARDT textures.
DEFAULT_PRESETS = [
    ("body", 496, "Car body"),
    ("shadow", 503, "Semi-transparent / shadow"),
    ("tire", 504, "Tires"),
]


class ClutPreset:
    __slots__ = ('name', 'clut_x', 'clut_y', 'description')

    def __init__(self, name, clut_x, clut_y, description=""):
        self.name = name
        self.clut_x = int(clut_x)
        self.clut_y = int(clut_y)
        self.description = description or ""

    @property
    def model_clut_x(self):
        """CLUT X as 00000000.BIN stores it (VRAM X / 16)."""
        return self.clut_x // 16


class ClutPresetTable:
    """A parsed clut_presets.json, or the built-in fallback."""

    def __init__(self, presets, source="<built-in>"):
        self.presets = list(presets)
        self.source = source
        self._by_name = {p.name: p for p in self.presets}

    def get(self, name):
        return self._by_name.get(name)

    def resolve(self, name):
        """(model_clut_x, clut_y) for *name*, or None when it is unknown."""
        preset = self.get(name)
        if preset is None:
            return None
        return (preset.model_clut_x, preset.clut_y)

    def match(self, model_clut_x, clut_y):
        """Name of the first slot matching these raw model coordinates."""
        for preset in self.presets:
            if preset.model_clut_x == model_clut_x and preset.clut_y == clut_y:
                return preset.name
        return None

    def names(self):
        return [p.name for p in self.presets]


def builtin_table():
    return ClutPresetTable(
        [ClutPreset(name, DEFAULT_CLUT_VRAM_X, y, desc)
         for name, y, desc in DEFAULT_PRESETS],
        source="<built-in>",
    )


def parse_table(data, source):
    """Build a ClutPresetTable from already-decoded JSON *data*."""
    presets = []
    seen = set()
    for entry in data.get("presets", []):
        name = str(entry["name"])
        clut_x = int(entry.get("clut_x", DEFAULT_CLUT_VRAM_X))
        clut_y = int(entry["clut_y"])
        if clut_x % 16 != 0:
            raise ValueError(
                f"{source}: slot '{name}' has clut_x {clut_x}, which is not a "
                f"multiple of 16. The model file can only store multiples of 16.")
        if not 0 <= clut_y <= 511:
            raise ValueError(
                f"{source}: slot '{name}' has clut_y {clut_y}, outside 0-511.")
        if name in seen:
            raise ValueError(f"{source}: duplicate slot name '{name}'.")
        seen.add(name)
        presets.append(ClutPreset(name, clut_x, clut_y, entry.get("note", "")))

    if not presets:
        raise ValueError(f"{source}: no slots defined.")
    return ClutPresetTable(presets, source)


def load_table(path):
    """Load *path*. Returns (table, warning) and never raises: an unreadable
    file falls back to the built-in slots and reports why."""
    if not path:
        return builtin_table(), None
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(path):
        return builtin_table(), (
            f"CLUT preset file not found: {path}. Using the built-in slots.")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return parse_table(json.load(f), path), None
    except Exception as exc:
        return builtin_table(), (
            f"Could not read CLUT presets from {path}: {exc}. "
            f"Using the built-in slots.")


def sibling_preset_file(model_path):
    """The clut_presets.json next to a model file, if rcardt-unpack made one."""
    candidate = os.path.join(os.path.dirname(model_path), JSON_FILENAME)
    return candidate if os.path.isfile(candidate) else ""


# ---------------------------------------------------------------------------
# Cache. Blender rebuilds enum items on every redraw, so the JSON must not be
# re-read each time.
# ---------------------------------------------------------------------------

_cache = None
_cache_key = None


def get_table(path):
    global _cache, _cache_key
    key = path or ""
    if _cache is None or _cache_key != key:
        _cache, _ = load_table(path)
        _cache_key = key
    return _cache


def invalidate_cache():
    global _cache, _cache_key
    _cache = None
    _cache_key = None
