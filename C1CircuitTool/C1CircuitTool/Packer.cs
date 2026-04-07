using AuroraLib.Compression.Formats.Common;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

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
            Console.WriteLine("Startin to Pack...");

            Directory.CreateDirectory(_destPath);

            using (FileStream arcFileStream = new FileStream(_inputPath, FileMode.Create, FileAccess.Write))
            {
                string[] inputPaths = Directory.GetFiles(_inputPath);
                if (inputPaths.Length < 1)
                {
                    return;
                }
                arcFileStream.Write(BitConverter.GetBytes(inputPaths.Length));
                long sizesArrayPos = arcFileStream.Position;
                arcFileStream.Seek(inputPaths.Length * 4, SeekOrigin.Current);



            }

        }

    }
}
