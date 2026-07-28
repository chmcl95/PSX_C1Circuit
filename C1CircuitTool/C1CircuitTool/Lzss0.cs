using System;
using System.IO;

namespace C1CircuitTool
{
    /// <summary>
    /// LZSS variant used by C1 Circuit's ".S" archives, matching QuickBMS'
    /// "comType LZSS0" and the classic Haruhiko Okumura reference decoder.
    ///
    /// The important detail is the ring buffer: 4096 bytes pre-filled with
    /// 0x00, with the write cursor starting at N - F (4078) rather than 0.
    /// Compressed streams reference that virgin dictionary to encode runs of
    /// zeroes near the start of a file, so a decoder that models the window
    /// differently silently produces wrong bytes there and nowhere else.
    ///
    /// AuroraLib.Compression 2.0.0 gets this wrong, which is why the previous
    /// implementation produced valid-looking model files (00000000.BIN never
    /// hits the virgin window) but corrupt texture files (00000001.BIN does).
    /// 16 of the 17 retail RCARDT archives were affected.
    ///
    /// Compression is still handed to AuroraLib: an encoder never needs to
    /// emit a reference into the virgin dictionary, and its output was
    /// verified to decode byte-identically through this decoder.
    /// </summary>
    static class Lzss0
    {
        private const int N = 4096;         // ring buffer size
        private const int F = 18;           // longest match
        private const int Threshold = 2;    // shortest encoded match
        private const byte InitialFill = 0x00;

        public static byte[] Decompress(ReadOnlySpan<byte> source, int decompressedSize)
        {
            if (decompressedSize < 0)
            {
                throw new InvalidDataException(
                    $"Negative decompressed size ({decompressedSize}).");
            }

            byte[] window = new byte[N];
            if (InitialFill != 0x00)
            {
                window.AsSpan().Fill(InitialFill);
            }

            byte[] output = new byte[decompressedSize];
            int outPos = 0;
            int srcPos = 0;
            int cursor = N - F;
            uint flags = 0;

            while (outPos < decompressedSize)
            {
                // The low byte of `flags` holds the control bits; the 0xFF00
                // marker tells us when all 8 have been consumed.
                flags >>= 1;
                if ((flags & 0x100) == 0)
                {
                    if (srcPos >= source.Length) break;
                    flags = (uint)(source[srcPos++] | 0xFF00);
                }

                if ((flags & 1) != 0)
                {
                    // Literal byte.
                    if (srcPos >= source.Length) break;
                    byte c = source[srcPos++];
                    output[outPos++] = c;
                    window[cursor] = c;
                    cursor = (cursor + 1) & (N - 1);
                }
                else
                {
                    // Back reference: 12 bit offset + 4 bit length.
                    if (srcPos + 1 >= source.Length) break;
                    int offset = source[srcPos++];
                    int lengthByte = source[srcPos++];
                    offset |= (lengthByte & 0xF0) << 4;
                    int length = (lengthByte & 0x0F) + Threshold;

                    for (int k = 0; k <= length; k++)
                    {
                        byte c = window[(offset + k) & (N - 1)];
                        output[outPos++] = c;
                        window[cursor] = c;
                        cursor = (cursor + 1) & (N - 1);
                        if (outPos >= decompressedSize) break;
                    }
                }
            }

            if (outPos != decompressedSize)
            {
                throw new InvalidDataException(
                    $"Compressed stream ended early: produced {outPos} of " +
                    $"{decompressedSize} bytes.");
            }
            return output;
        }
    }
}
