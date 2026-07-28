using System;
using System.Collections.Generic;
using System.IO;

namespace C1CircuitTool.Rcardt
{
    /// <summary>
    /// One VRAM upload block, the single building brick of 00000001.BIN.
    ///
    /// <code>
    /// uint32 size   // payload bytes == Width * Height * 2
    /// uint16 vramX  // destination X in VRAM (pixels for a CLUT, halfwords for pixels)
    /// uint16 vramY  // destination Y in VRAM
    /// uint16 width  // in 16 bit words
    /// uint16 height // in scanlines
    /// byte[] payload
    /// </code>
    ///
    /// This is the TIM/CLT/PXL "data section" with one difference: TIM's
    /// <c>bnum</c> counts the 12 byte header too, C1's <c>size</c> does not.
    /// That 12 is the entire conversion between the two formats.
    ///
    /// The blocks strictly alternate CLUT, pixels, CLUT, pixels ... and tile
    /// the file exactly with no terminator (verified against all 17 retail
    /// RCARDT archives). Store order is VRAM upload order, so later blocks
    /// overwrite earlier ones.
    /// </summary>
    class VramBlock
    {
        public const int HeaderSize = 12;

        public ushort VramX { get; set; }
        public ushort VramY { get; set; }
        public ushort Width { get; set; }      // 16 bit words
        public ushort Height { get; set; }
        public byte[] Payload { get; set; }

        public int PayloadSize => Width * Height * 2;

        /// <summary>Pixel width once 4bpp packing is undone (4 pixels per word).</summary>
        public int PixelWidth4Bpp => Width * 4;

        /// <summary>A CLUT block is 16 colours wide; Height is the palette count.</summary>
        public bool LooksLikeClut => Width == 16 && VramY >= 480;

        public static VramBlock Read(ReadOnlySpan<byte> data, int offset, string context)
        {
            if (offset + HeaderSize > data.Length)
            {
                throw new InvalidDataException(
                    $"{context}: block header at {offset:X} runs past the end of " +
                    $"the {data.Length} byte file.");
            }

            int size = BitConverter.ToInt32(data.Slice(offset, 4));
            var block = new VramBlock
            {
                VramX = BitConverter.ToUInt16(data.Slice(offset + 4, 2)),
                VramY = BitConverter.ToUInt16(data.Slice(offset + 6, 2)),
                Width = BitConverter.ToUInt16(data.Slice(offset + 8, 2)),
                Height = BitConverter.ToUInt16(data.Slice(offset + 10, 2)),
            };

            if (size != block.PayloadSize)
            {
                throw new InvalidDataException(
                    $"{context}: block at 0x{offset:X} declares {size} payload bytes " +
                    $"but {block.Width}x{block.Height} words is {block.PayloadSize}. " +
                    $"The file is corrupt or is not a 00000001.BIN texture file.");
            }
            if (offset + HeaderSize + size > data.Length)
            {
                throw new InvalidDataException(
                    $"{context}: block at 0x{offset:X} needs {size} payload bytes but " +
                    $"only {data.Length - offset - HeaderSize} remain.");
            }

            block.Payload = data.Slice(offset + HeaderSize, size).ToArray();
            return block;
        }

        public void Write(Stream stream)
        {
            if (Payload.Length != PayloadSize)
            {
                throw new InvalidDataException(
                    $"Block at VRAM ({VramX},{VramY}): payload is {Payload.Length} " +
                    $"bytes but {Width}x{Height} words needs {PayloadSize}.");
            }
            stream.Write(BitConverter.GetBytes(Payload.Length));
            stream.Write(BitConverter.GetBytes(VramX));
            stream.Write(BitConverter.GetBytes(VramY));
            stream.Write(BitConverter.GetBytes(Width));
            stream.Write(BitConverter.GetBytes(Height));
            stream.Write(Payload);
        }

        public static List<VramBlock> ReadAll(byte[] data, string context)
        {
            var blocks = new List<VramBlock>();
            int offset = 0;
            while (offset < data.Length)
            {
                var block = Read(data, offset, context);
                blocks.Add(block);
                offset += HeaderSize + block.Payload.Length;
            }
            if (offset != data.Length)
            {
                throw new InvalidDataException(
                    $"{context}: {data.Length - offset} trailing byte(s) after the " +
                    $"last block.");
            }
            return blocks;
        }
    }
}
