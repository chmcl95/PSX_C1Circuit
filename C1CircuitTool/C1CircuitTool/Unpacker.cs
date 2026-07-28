using System;
using System.IO;

namespace C1CircuitTool
{
    class Unpacker
    {
        private string _inputPath;
        private string _destPath;

        public Unpacker(string inputPath, string destPath)
        {
            _inputPath = inputPath;
            _destPath = destPath;
        }

        public void Unpack()
        {
            Console.WriteLine("Starting Unpack...");

            Directory.CreateDirectory(_destPath);

            var entries = SFile.Read(_inputPath);
            for (int i = 0; i < entries.Count; i++)
            {
                File.WriteAllBytes(Path.Combine(_destPath, $"{i:D8}.BIN"), entries[i]);
            }

            Console.WriteLine($"Done ({entries.Count} file(s))");
        }
    }
}
