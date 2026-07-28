using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace C1CircuitTool.Rcardt
{
    /// <summary>
    /// One texture's slot: which TIM holds it and where both halves land in
    /// VRAM. This is the single place a palette position is written down.
    ///
    /// The model (00000000.BIN) stores the CLUT X divided by 16 while the
    /// texture (00000001.BIN) stores it as-is, which is exactly the
    /// duplication this file removes: the Blender addon reads the same JSON
    /// and derives its own encoding.
    /// </summary>
    class ClutPreset
    {
        [JsonPropertyName("name")]
        public string Name { get; set; }

        [JsonPropertyName("file")]
        public string File { get; set; }

        [JsonPropertyName("clut_x")]
        public int ClutX { get; set; }

        [JsonPropertyName("clut_y")]
        public int ClutY { get; set; }

        [JsonPropertyName("pixel_x")]
        public int PixelX { get; set; }

        [JsonPropertyName("pixel_y")]
        public int PixelY { get; set; }

        [JsonPropertyName("note")]
        public string Note { get; set; }

        /// <summary>CLUT X as the model file stores it (VRAM X / 16).</summary>
        [JsonIgnore]
        public int ModelClutX => ClutX / 16;
    }

    class ClutPresetFile
    {
        public const string DefaultFileName = "clut_presets.json";

        [JsonPropertyName("version")]
        public int Version { get; set; } = 1;

        [JsonPropertyName("comment")]
        public string[] Comment { get; set; }

        [JsonPropertyName("presets")]
        public List<ClutPreset> Presets { get; set; } = new List<ClutPreset>();

        private static readonly string[] HelpText =
        {
            "CLUT slot definition for one RCARDT car, written by 'rcardt-unpack'.",
            "",
            "Each entry pairs a TIM file with the VRAM position of its palette and",
            "pixels. 'rcardt-pack' rebuilds 00000001.BIN from these coordinates, and",
            "the Blender addon offers 'name' as the material's CLUT slot, writing",
            "clut_x / 16 into the model. Moving a palette here therefore moves it on",
            "both sides at once.",
            "",
            "  clut_x  : VRAM X of the palette, a multiple of 16 (the model field",
            "            only stores x/16). Retail data always uses 128.",
            "  clut_y  : VRAM scanline of the palette. Retail data uses 496-511;",
            "            496 = body, 503 = semi-transparent / shadow, 504 = tires.",
            "  pixel_x : VRAM X of the pixel data, counted in 16 bit words.",
            "  pixel_y : VRAM scanline of the pixel data.",
            "",
            "Entry order is VRAM upload order: later entries overwrite earlier ones.",
            "Pixel width/height come from the TIM itself, so resizing an image in",
            "ps-image needs no change here.",
        };

        public static ClutPresetFile Load(string path)
        {
            string json;
            try
            {
                json = System.IO.File.ReadAllText(path);
            }
            catch (Exception e)
            {
                throw new InvalidDataException($"Could not read '{path}': {e.Message}");
            }

            ClutPresetFile result;
            try
            {
                result = JsonSerializer.Deserialize<ClutPresetFile>(json,
                    new JsonSerializerOptions { ReadCommentHandling = JsonCommentHandling.Skip });
            }
            catch (JsonException e)
            {
                throw new InvalidDataException($"'{path}' is not valid JSON: {e.Message}");
            }

            if (result?.Presets == null || result.Presets.Count == 0)
            {
                throw new InvalidDataException($"'{path}' defines no presets.");
            }

            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var preset in result.Presets)
            {
                if (string.IsNullOrWhiteSpace(preset.Name))
                {
                    throw new InvalidDataException($"'{path}': a preset has no name.");
                }
                if (!seen.Add(preset.Name))
                {
                    throw new InvalidDataException(
                        $"'{path}': duplicate preset name '{preset.Name}'.");
                }
                if (string.IsNullOrWhiteSpace(preset.File))
                {
                    throw new InvalidDataException(
                        $"'{path}': preset '{preset.Name}' names no TIM file.");
                }
                if (preset.ClutX % 16 != 0)
                {
                    throw new InvalidDataException(
                        $"'{path}': preset '{preset.Name}' has clut_x {preset.ClutX}, " +
                        $"which is not a multiple of 16. The model file can only " +
                        $"store multiples of 16.");
                }
                if (preset.ClutY < 0 || preset.ClutY > 511)
                {
                    throw new InvalidDataException(
                        $"'{path}': preset '{preset.Name}' has clut_y {preset.ClutY}, " +
                        $"outside the 0-511 VRAM range.");
                }
            }
            return result;
        }

        public void Save(string path)
        {
            Comment = HelpText;
            var options = new JsonSerializerOptions
            {
                WriteIndented = true,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
            };
            System.IO.File.WriteAllText(path, JsonSerializer.Serialize(this, options));
        }

        /// <summary>
        /// The player car owns VRAM X 640-703; 704 and up belongs to the rival
        /// cars and writing there corrupts them. Warn rather than fail, since
        /// only the game can say for sure.
        /// </summary>
        public IEnumerable<string> VramWarnings()
        {
            foreach (var preset in Presets)
            {
                if (preset.PixelX >= 704)
                {
                    yield return $"'{preset.Name}': pixel X {preset.PixelX} is at or " +
                                 $"past 704, which belongs to the rival cars.";
                }
            }
        }
    }
}
