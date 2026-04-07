using AuroraLib.Compression;
using AuroraLib.Compression.Formats.Common;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

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
            Console.WriteLine("Startin to unpack...");

            Directory.CreateDirectory(_destPath);

            using (FileStream arcFileStream = new FileStream(_inputPath, FileMode.Open, FileAccess.Read))
            {
                byte[] bytes = new byte[4];
                arcFileStream.Read(bytes);
                Int32 length = BitConverter.ToInt32(bytes);
                Int32[] compressedSizes = new Int32[length];

                for (int i = 0; i < length; i++)
                {
                    arcFileStream.Read(bytes);
                    Int32 size = BitConverter.ToInt32(bytes);
                    compressedSizes[i] = size;
                }
                for (int i = 0; i < length; i++)
                {
                    bytes = new byte[4];
                    arcFileStream.Read(bytes, 0x00, bytes.Length);
                    Int32 decompressSize = BitConverter.ToInt32(bytes);
                    bytes = new byte[compressedSizes[i]-4];
                    arcFileStream.Read(bytes, 0x00, bytes.Length);
                    using (MemoryStream sourceStream = new MemoryStream(bytes))
                    using (FileStream destStream = new FileStream(@$"{_destPath}\{i:D8}.BIN", FileMode.Create, FileAccess.Write))
                    {
                        LzProperties lzProperties = new LzProperties(0x1000, 0xF + 3, 3, 0xFEE);
                        LZSS.DecompressHeaderless(sourceStream, destStream, (uint)decompressSize, lzProperties);
                    }
                }
            }

        }
    }
}
