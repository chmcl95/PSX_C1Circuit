using System;
using System.Collections.Generic;
using System.IO;

namespace C1CircuitTool.Rcardt
{
    /// <summary>
    /// Rebuilds an RCARDT car archive from a working folder produced by
    /// rcardt-unpack: 00000000.BIN plus the TIMs listed in clut_presets.json.
    /// </summary>
    class RcardtPacker
    {
        private readonly string _inputPath;
        private readonly string _destPath;
        private readonly string _presetPath;

        public RcardtPacker(string inputPath, string destPath, string presetPath)
        {
            _inputPath = inputPath;
            _destPath = destPath;
            _presetPath = presetPath;
        }

        public void Pack()
        {
            string presetPath = ResolvePresetPath();
            Console.WriteLine($"Packing '{_inputPath}' ...");
            Console.WriteLine($"  presets: {presetPath}");

            var presetFile = ClutPresetFile.Load(presetPath);

            string modelPath = Path.Combine(_inputPath, RcardtUnpacker.ModelFileName);
            if (!File.Exists(modelPath))
            {
                throw new FileNotFoundException(
                    $"'{RcardtUnpacker.ModelFileName}' is missing from '{_inputPath}'. " +
                    $"Export the model from Blender into this folder first.");
            }
            byte[] model = File.ReadAllBytes(modelPath);
            Console.WriteLine($"  {RcardtUnpacker.ModelFileName,-16} {model.Length,7} bytes");

            byte[] texture = BuildTexture(presetFile);

            Directory.CreateDirectory(_destPath);
            string outputPath = Path.Combine(
                _destPath, $"{new DirectoryInfo(_inputPath).Name}.S");
            SFile.Write(outputPath, new List<byte[]> { model, texture });

            foreach (string warning in presetFile.VramWarnings())
            {
                Console.WriteLine($"  ! {warning}");
            }

            Console.WriteLine($"Done -> {outputPath}");
        }

        private string ResolvePresetPath()
        {
            if (!string.IsNullOrEmpty(_presetPath))
            {
                if (!File.Exists(_presetPath))
                {
                    throw new FileNotFoundException(
                        $"The preset file '{_presetPath}' does not exist.");
                }
                return _presetPath;
            }

            string inFolder = Path.Combine(_inputPath, ClutPresetFile.DefaultFileName);
            if (!File.Exists(inFolder))
            {
                throw new FileNotFoundException(
                    $"'{ClutPresetFile.DefaultFileName}' was not found in " +
                    $"'{_inputPath}'. Unpack the car with 'rcardt-unpack' first, or " +
                    $"point --presets at an existing one.");
            }
            return inFolder;
        }

        private byte[] BuildTexture(ClutPresetFile presetFile)
        {
            using var stream = new MemoryStream();
            int index = 0;
            foreach (var preset in presetFile.Presets)
            {
                string timPath = Path.Combine(_inputPath, preset.File);
                if (!File.Exists(timPath))
                {
                    throw new FileNotFoundException(
                        $"Preset '{preset.Name}' refers to '{preset.File}', which is " +
                        $"not in '{_inputPath}'. Rename the file back, or update the " +
                        $"'file' field in {ClutPresetFile.DefaultFileName}.");
                }

                TimFile.Read(timPath, out VramBlock clut, out VramBlock pixels);

                // The preset file is the authority on placement: ps-image cannot
                // edit the coordinates inside a TIM, so whatever it wrote there
                // is ignored.
                clut.VramX = (ushort)preset.ClutX;
                clut.VramY = (ushort)preset.ClutY;
                pixels.VramX = (ushort)preset.PixelX;
                pixels.VramY = (ushort)preset.PixelY;

                clut.Write(stream);
                pixels.Write(stream);

                Console.WriteLine(
                    $"  [{index:D3}] {preset.File,-40} CLUT({clut.VramX},{clut.VramY}) " +
                    $"x{clut.Height}  pixels({pixels.VramX},{pixels.VramY}) " +
                    $"{pixels.PixelWidth4Bpp}x{pixels.Height}");
                index++;
            }

            byte[] texture = stream.ToArray();
            Console.WriteLine($"  {RcardtUnpacker.TextureFileName,-16} {texture.Length,7} " +
                              $"bytes  ({presetFile.Presets.Count} texture(s))");
            return texture;
        }
    }
}
