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
            Console.WriteLine("Starting Pack...");

            Directory.CreateDirectory(_destPath);

            using (FileStream arcFileStream = new FileStream(@$"{_destPath}\{Path.GetFileNameWithoutExtension(_inputPath)}.S", FileMode.Create, FileAccess.Write))
            {
                string[] inputPaths = Directory.GetFiles(_inputPath);
                if (inputPaths.Length < 1)
                {
                    return;
                }
                arcFileStream.Write(BitConverter.GetBytes(inputPaths.Length));
                long sizesArrayPos = arcFileStream.Position;
                arcFileStream.Seek(inputPaths.Length * 4, SeekOrigin.Current);
                UInt32[] compressedSizes = new UInt32[inputPaths.Length];
                for (int i = 0; i < inputPaths.Length; i++)
                {
                    using (FileStream sourceStream = new FileStream(inputPaths[i], FileMode.Open, FileAccess.Read))
                    using (MemoryStream destStream = new MemoryStream())
                    {
                        byte[] bytes = new byte[sourceStream.Length];
                        sourceStream.Read(bytes, 0x00, bytes.Length);
                        LZSS.CompressHeaderless(bytes, destStream, LZSS.Lzss0Properties, AuroraLib.Compression.CompressionSettings.Maximum);
                        long fileStartPos = arcFileStream.Position;
                        // decompressedSize
                        bytes = new byte[4];
                        bytes = BitConverter.GetBytes((UInt32)sourceStream.Length);
                        arcFileStream.Write(bytes);
                        // compressedData
                        bytes = destStream.ToArray();
                        arcFileStream.Write(bytes);
                        //// padding
                        while ((arcFileStream.Position % 4) != 0)
                        {
                            bytes[0] = 0x00;
                            arcFileStream.Write(bytes, 0x00, bytes.Length);
                        }
                        long fileEndPos = arcFileStream.Position;
                        compressedSizes[i] = (UInt32)(fileEndPos - fileStartPos);

                    }
                }
                arcFileStream.Seek(sizesArrayPos, SeekOrigin.Begin);
                for(int i = 0; i < inputPaths.Length; i++)
                {
                    byte[] bytes = new byte[4];
                    bytes = BitConverter.GetBytes(compressedSizes[i]);
                    arcFileStream.Write(bytes);
                }

            }

            Console.WriteLine("Done");
        }

    }
}
