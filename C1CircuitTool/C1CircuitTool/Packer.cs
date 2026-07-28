using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace C1CircuitTool
{
    class Packer
    {
        private string _inputPath;
        private string _destPath;

        public Packer(string inputPath, string destPath)
        {
            _inputPath = inputPath;
            _destPath = destPath;
        }

        public void Pack()
        {
            Console.WriteLine("Starting Pack...");

            // Entry order is the archive's index order, which the game relies
            // on (00000000 = model, 00000001 = texture). Sort by name so it
            // never depends on the order the filesystem happens to return.
            string[] inputPaths = Directory.GetFiles(_inputPath)
                .OrderBy(Path.GetFileName, StringComparer.Ordinal)
                .ToArray();
            if (inputPaths.Length < 1)
            {
                Console.WriteLine($"No files found in '{_inputPath}'.");
                return;
            }

            foreach (string path in inputPaths)
            {
                Console.WriteLine($"  + {Path.GetFileName(path)}");
            }

            Directory.CreateDirectory(_destPath);

            var entries = new List<byte[]>(inputPaths.Length);
            foreach (string path in inputPaths)
            {
                entries.Add(File.ReadAllBytes(path));
            }

            string outputPath = Path.Combine(
                _destPath, $"{Path.GetFileNameWithoutExtension(_inputPath)}.S");
            SFile.Write(outputPath, entries);

            Console.WriteLine($"Done -> {outputPath}");
        }
    }
}
