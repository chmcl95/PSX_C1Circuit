using System;
using System.IO;

namespace C1CircuitTool.Rcardt
{
    /// <summary>
    /// Sony TIM (file ID 0x10), the interchange format for editing RCARDT
    /// textures in ps-image and friends.
    ///
    /// <code>
    /// uint8  id        = 0x10
    /// uint8  version   = 0x00
    /// uint16 reserved  = 0x0000
    /// uint32 flags       // bit0-2 = pixel type, bit3 = has CLUT
    /// [CLUT section]     // uint32 bnum(= payload + 12), uint16 dx, dy, w, h, payload
    /// [Pixel section]
    /// </code>
    ///
    /// Every RCARDT texture is 4bpp with a 16 colour CLUT, so the flags word
    /// is always 0x00000008 (type 0 = 4bpp, plus HasCLUT).
    ///
    /// The destination coordinates in the section headers are preserved, but
    /// ps-image cannot edit them, so rcardt-pack takes the authoritative VRAM
    /// placement from clut_presets.json instead.
    /// </summary>
    static class TimFile
    {
        private const byte Id = 0x10;
        private const int HeaderSize = 8;
        private const int SectionHeaderSize = 12;

        public const int PixelType4Bpp = 0;
        private const uint FlagHasClut = 1u << 3;

        public static void Write(string path, VramBlock clut, VramBlock pixels)
        {
            using var stream = new FileStream(path, FileMode.Create, FileAccess.Write);
            stream.WriteByte(Id);
            stream.WriteByte(0x00);
            stream.Write(BitConverter.GetBytes((ushort)0));
            stream.Write(BitConverter.GetBytes((uint)PixelType4Bpp | FlagHasClut));
            WriteSection(stream, clut);
            WriteSection(stream, pixels);
        }

        private static void WriteSection(Stream stream, VramBlock block)
        {
            stream.Write(BitConverter.GetBytes(block.Payload.Length + SectionHeaderSize));
            stream.Write(BitConverter.GetBytes(block.VramX));
            stream.Write(BitConverter.GetBytes(block.VramY));
            stream.Write(BitConverter.GetBytes(block.Width));
            stream.Write(BitConverter.GetBytes(block.Height));
            stream.Write(block.Payload);
        }

        public static void Read(string path, out VramBlock clut, out VramBlock pixels)
        {
            byte[] data = File.ReadAllBytes(path);
            string name = Path.GetFileName(path);

            if (data.Length < HeaderSize || data[0] != Id)
            {
                throw new InvalidDataException(
                    $"'{name}': expected a TIM file (first byte 0x10), got 0x{(data.Length > 0 ? data[0] : 0):X2}.");
            }

            uint flags = BitConverter.ToUInt32(data, 4);
            uint pixelType = flags & 0x7;
            if (pixelType != PixelType4Bpp)
            {
                throw new InvalidDataException(
                    $"'{name}': pixel type {pixelType} is not supported. RCARDT " +
                    $"textures are 4bpp (type 0) with a 16 colour CLUT.");
            }
            if ((flags & FlagHasClut) == 0)
            {
                throw new InvalidDataException(
                    $"'{name}': the TIM has no CLUT section. RCARDT textures need one.");
            }

            int offset = HeaderSize;
            clut = ReadSection(data, ref offset, name, "CLUT");
            pixels = ReadSection(data, ref offset, name, "pixel");

            if (offset != data.Length)
            {
                Console.WriteLine(
                    $"  ! '{name}': ignoring {data.Length - offset} trailing byte(s) " +
                    $"after the pixel section.");
            }
            if (clut.Width != 16)
            {
                throw new InvalidDataException(
                    $"'{name}': the CLUT is {clut.Width} colours wide; RCARDT needs " +
                    $"exactly 16 (4bpp).");
            }
        }

        private static VramBlock ReadSection(byte[] data, ref int offset, string name,
                                             string what)
        {
            if (offset + SectionHeaderSize > data.Length)
            {
                throw new InvalidDataException(
                    $"'{name}': the {what} section header is truncated.");
            }
            int bnum = BitConverter.ToInt32(data, offset);
            int payloadSize = bnum - SectionHeaderSize;
            var block = new VramBlock
            {
                VramX = BitConverter.ToUInt16(data, offset + 4),
                VramY = BitConverter.ToUInt16(data, offset + 6),
                Width = BitConverter.ToUInt16(data, offset + 8),
                Height = BitConverter.ToUInt16(data, offset + 10),
            };

            if (payloadSize < 0 || offset + bnum > data.Length)
            {
                throw new InvalidDataException(
                    $"'{name}': the {what} section declares {bnum} bytes, which does " +
                    $"not fit in the {data.Length} byte file.");
            }
            if (payloadSize != block.PayloadSize)
            {
                throw new InvalidDataException(
                    $"'{name}': the {what} section holds {payloadSize} bytes but its " +
                    $"{block.Width}x{block.Height} word size needs {block.PayloadSize}.");
            }

            block.Payload = new byte[payloadSize];
            Array.Copy(data, offset + SectionHeaderSize, block.Payload, 0, payloadSize);
            offset += bnum;
            return block;
        }
    }
}
