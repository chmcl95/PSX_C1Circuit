using AuroraLib.Compression.Formats.Common;
using System;
using System.Collections.Generic;
using System.IO;

namespace C1CircuitTool
{
    /// <summary>
    /// The ".S" container: a count, a table of per-entry byte lengths, then
    /// the entries themselves.
    ///
    /// <code>
    /// int32   entryCount
    /// int32[] entrySize     // bytes occupied by each entry, padding included
    /// // repeated entryCount times:
    /// int32   decompressedSize
    /// byte[]  lzss0Data     // entrySize - 4 bytes, padded to a 4 byte boundary
    /// </code>
    /// </summary>
    static class SFile
    {
        public static List<byte[]> Read(string path)
        {
            byte[] data = File.ReadAllBytes(path);
            if (data.Length < 4)
            {
                throw new InvalidDataException(
                    $"'{path}' is only {data.Length} bytes; too short to be a .S archive.");
            }

            int count = BitConverter.ToInt32(data, 0);
            if (count <= 0 || 4 + count * 4 > data.Length)
            {
                throw new InvalidDataException(
                    $"'{path}' declares {count} entries, which does not fit in " +
                    $"{data.Length} bytes. This is probably not a .S archive.");
            }

            var sizes = new int[count];
            for (int i = 0; i < count; i++)
            {
                sizes[i] = BitConverter.ToInt32(data, 4 + i * 4);
            }

            var entries = new List<byte[]>(count);
            int offset = 4 + count * 4;
            for (int i = 0; i < count; i++)
            {
                if (sizes[i] < 4 || offset + sizes[i] > data.Length)
                {
                    throw new InvalidDataException(
                        $"'{path}' entry {i}: size {sizes[i]} at offset {offset} " +
                        $"runs past the end of the {data.Length} byte file.");
                }
                int decompressedSize = BitConverter.ToInt32(data, offset);
                var compressed = new ReadOnlySpan<byte>(data, offset + 4, sizes[i] - 4);
                entries.Add(Lzss0.Decompress(compressed, decompressedSize));
                offset += sizes[i];
            }
            return entries;
        }

        public static void Write(string path, IReadOnlyList<byte[]> entries)
        {
            if (entries.Count == 0)
            {
                throw new ArgumentException("Refusing to write an empty .S archive.",
                                            nameof(entries));
            }

            using var stream = new FileStream(path, FileMode.Create, FileAccess.Write);
            stream.Write(BitConverter.GetBytes(entries.Count));

            long sizeTablePos = stream.Position;
            stream.Seek(entries.Count * 4, SeekOrigin.Current);

            var sizes = new uint[entries.Count];
            for (int i = 0; i < entries.Count; i++)
            {
                long start = stream.Position;

                using var compressed = new MemoryStream();
                LZSS.CompressHeaderless(entries[i], compressed, LZSS.Lzss0Properties,
                                        AuroraLib.Compression.CompressionSettings.Maximum);

                stream.Write(BitConverter.GetBytes((uint)entries[i].Length));
                stream.Write(compressed.ToArray());
                while ((stream.Position % 4) != 0)
                {
                    stream.WriteByte(0x00);
                }
                sizes[i] = (uint)(stream.Position - start);
            }

            stream.Seek(sizeTablePos, SeekOrigin.Begin);
            for (int i = 0; i < entries.Count; i++)
            {
                stream.Write(BitConverter.GetBytes(sizes[i]));
            }
        }
    }
}
