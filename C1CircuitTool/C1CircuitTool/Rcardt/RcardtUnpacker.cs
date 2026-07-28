using System;
using System.Collections.Generic;
using System.IO;

namespace C1CircuitTool.Rcardt
{
    /// <summary>
    /// Unpacks an RCARDT car archive into an editable working folder:
    /// the model as-is, the texture split into one TIM per palette+pixel
    /// pair, and the clut_presets.json that ties them together.
    /// </summary>
    class RcardtUnpacker
    {
        public const string ModelFileName = "00000000.BIN";
        public const string TextureFileName = "00000001.BIN";

        private readonly string _inputPath;
        private readonly string _destPath;
        private readonly bool _keepRawTexture;

        public RcardtUnpacker(string inputPath, string destPath, bool keepRawTexture)
        {
            _inputPath = inputPath;
            _destPath = destPath;
            _keepRawTexture = keepRawTexture;
        }

        public void Unpack()
        {
            Console.WriteLine($"Unpacking '{Path.GetFileName(_inputPath)}' ...");

            var entries = SFile.Read(_inputPath);
            if (entries.Count != 2)
            {
                throw new InvalidDataException(
                    $"'{_inputPath}' holds {entries.Count} file(s). An RCARDT car " +
                    $"archive holds exactly 2 (model + texture). Use the plain " +
                    $"'unpack' verb for other archives.");
            }

            Directory.CreateDirectory(_destPath);

            string modelPath = Path.Combine(_destPath, ModelFileName);
            File.WriteAllBytes(modelPath, entries[0]);
            Console.WriteLine($"  {ModelFileName,-16} {entries[0].Length,7} bytes  (model)");

            if (_keepRawTexture)
            {
                File.WriteAllBytes(Path.Combine(_destPath, TextureFileName), entries[1]);
            }

            var blocks = VramBlock.ReadAll(entries[1], TextureFileName);
            if (blocks.Count % 2 != 0)
            {
                throw new InvalidDataException(
                    $"{TextureFileName}: {blocks.Count} blocks. They must come in " +
                    $"CLUT + pixel pairs.");
            }

            var presetFile = new ClutPresetFile();
            for (int i = 0; i < blocks.Count; i += 2)
            {
                VramBlock clut = blocks[i];
                VramBlock pixels = blocks[i + 1];

                if (!clut.LooksLikeClut)
                {
                    throw new InvalidDataException(
                        $"{TextureFileName}: block {i} at VRAM ({clut.VramX},{clut.VramY}) " +
                        $"is {clut.Width} words wide; expected a 16 colour CLUT.");
                }

                int index = i / 2;
                string name = MakeName(index, clut, pixels);
                string fileName = name + ".TIM";
                TimFile.Write(Path.Combine(_destPath, fileName), clut, pixels);

                presetFile.Presets.Add(new ClutPreset
                {
                    Name = name,
                    File = fileName,
                    ClutX = clut.VramX,
                    ClutY = clut.VramY,
                    PixelX = pixels.VramX,
                    PixelY = pixels.VramY,
                    Note = $"{clut.Height} palette(s), " +
                           $"{pixels.PixelWidth4Bpp}x{pixels.Height} px 4bpp",
                });

                Console.WriteLine(
                    $"  {fileName,-40} CLUT({clut.VramX},{clut.VramY}) x{clut.Height}  " +
                    $"pixels({pixels.VramX},{pixels.VramY}) " +
                    $"{pixels.PixelWidth4Bpp}x{pixels.Height}");
            }

            string presetPath = Path.Combine(_destPath, ClutPresetFile.DefaultFileName);
            presetFile.Save(presetPath);
            Console.WriteLine($"  {ClutPresetFile.DefaultFileName,-16} " +
                              $"{presetFile.Presets.Count} slot(s)");

            foreach (string warning in presetFile.VramWarnings())
            {
                Console.WriteLine($"  ! {warning}");
            }

            Console.WriteLine($"Done -> {_destPath}");
        }

        /// <summary>
        /// Palette rows whose purpose is known from the retail data, so the
        /// generated slot names read as something rather than as coordinates.
        /// </summary>
        private static string SlotName(int clutY)
        {
            switch (clutY)
            {
                case 496: return "body";
                case 503: return "shadow";
                case 504: return "tire";
                default: return $"clut{clutY}";
            }
        }

        /// <summary>
        /// Short, sortable, unique name. The numeric prefix is the VRAM upload
        /// order, which is the one thing that must not change; everything else
        /// is free to rename as long as clut_presets.json is updated to match.
        /// The VRAM coordinates deliberately live in the JSON, where they can
        /// be edited, rather than in the file name.
        /// </summary>
        private static string MakeName(int index, VramBlock clut, VramBlock pixels)
        {
            return $"{index:D3}_{SlotName(clut.VramY)}" +
                   $"_{pixels.PixelWidth4Bpp}x{pixels.Height}";
        }
    }
}
