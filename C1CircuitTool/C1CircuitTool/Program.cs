using C1CircuitTool.Rcardt;
using CommandLine;
using System;
using System.IO;

namespace C1CircuitTool
{
    class Program
    {
        static int Main(string[] args)
        {
            Console.WriteLine("C1 Circuit Tool - by chmcl95");
            Console.WriteLine();

            return Parser.Default
                .ParseArguments<UnpackVerbs, PackVerbs, RcardtUnpackVerbs, RcardtPackVerbs>(args)
                .MapResult(
                    (UnpackVerbs o) => Run(() => Unpack(o)),
                    (PackVerbs o) => Run(() => Pack(o)),
                    (RcardtUnpackVerbs o) => Run(() => RcardtUnpack(o)),
                    (RcardtPackVerbs o) => Run(() => RcardtPack(o)),
                    _ => 1);
        }

        private static int Run(Action action)
        {
            try
            {
                action();
                return 0;
            }
            catch (Exception e) when (e is IOException || e is InvalidDataException ||
                                      e is ArgumentException)
            {
                Console.Error.WriteLine($"Error: {e.Message}");
                return 1;
            }
        }

        public static void Unpack(UnpackVerbs options)
        {
            if (!File.Exists(options.InputPath))
            {
                throw new FileNotFoundException($"'{options.InputPath}' does not exist.");
            }
            string outputPath = options.OutputPath;
            if (string.IsNullOrEmpty(outputPath))
            {
                outputPath = Path.Combine(
                    Path.GetDirectoryName(options.InputPath) ?? ".", "extracted",
                    Path.GetFileNameWithoutExtension(options.InputPath));
            }

            new Unpacker(options.InputPath, outputPath).Unpack();
        }

        public static void Pack(PackVerbs options)
        {
            if (!Directory.Exists(options.InputPath))
            {
                throw new DirectoryNotFoundException($"'{options.InputPath}' does not exist.");
            }

            string outputPath = options.OutputPath;
            if (string.IsNullOrEmpty(outputPath))
            {
                outputPath = Path.Combine(
                    Path.GetDirectoryName(options.InputPath.TrimEnd(
                        Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)) ?? ".",
                    "packed");
            }

            new Packer(options.InputPath, outputPath).Pack();
        }

        public static void RcardtUnpack(RcardtUnpackVerbs options)
        {
            if (!File.Exists(options.InputPath))
            {
                throw new FileNotFoundException($"'{options.InputPath}' does not exist.");
            }
            string outputPath = options.OutputPath;
            if (string.IsNullOrEmpty(outputPath))
            {
                outputPath = Path.Combine(
                    Path.GetDirectoryName(options.InputPath) ?? ".", "extracted",
                    Path.GetFileNameWithoutExtension(options.InputPath));
            }

            new RcardtUnpacker(options.InputPath, outputPath, options.KeepRawTexture).Unpack();
        }

        public static void RcardtPack(RcardtPackVerbs options)
        {
            if (!Directory.Exists(options.InputPath))
            {
                throw new DirectoryNotFoundException($"'{options.InputPath}' does not exist.");
            }

            string outputPath = options.OutputPath;
            if (string.IsNullOrEmpty(outputPath))
            {
                outputPath = Path.Combine(
                    Path.GetDirectoryName(options.InputPath.TrimEnd(
                        Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)) ?? ".",
                    "packed");
            }

            new RcardtPacker(options.InputPath, outputPath, options.PresetPath).Pack();
        }

        [Verb("unpack", HelpText = "Unpack any .S file into numbered .BIN files.")]
        public class UnpackVerbs
        {
            [Option('i', "input", Required = true, HelpText = "Input .S file like ALLCAR.S.")]
            public string InputPath { get; set; }

            [Option('o', "output", Required = false, HelpText = "Output directory for the extracted files.")]
            public string OutputPath { get; set; }
        }

        [Verb("pack", HelpText = "Pack a folder into a .S file. Files are added in ascending name order.")]
        public class PackVerbs
        {
            [Option('i', "input", Required = true, HelpText = "Input directory holding the files to pack.")]
            public string InputPath { get; set; }

            [Option('o', "output", Required = false, HelpText = "Output directory for the packed .S file.")]
            public string OutputPath { get; set; }
        }

        [Verb("rcardt-unpack", HelpText =
            "Unpack a car .S into an editable folder: 00000000.BIN, one .TIM per " +
            "texture, and clut_presets.json.")]
        public class RcardtUnpackVerbs
        {
            [Option('i', "input", Required = true, HelpText = "Input car .S file like NA8C.S.")]
            public string InputPath { get; set; }

            [Option('o', "output", Required = false, HelpText = "Output directory for the working files.")]
            public string OutputPath { get; set; }

            [Option("keep-raw-texture", Required = false, HelpText =
                "Also write the untouched 00000001.BIN next to the .TIM files.")]
            public bool KeepRawTexture { get; set; }
        }

        [Verb("rcardt-pack", HelpText =
            "Rebuild a car .S from a folder holding 00000000.BIN, the .TIM files and " +
            "clut_presets.json.")]
        public class RcardtPackVerbs
        {
            [Option('i', "input", Required = true, HelpText = "Working directory produced by rcardt-unpack.")]
            public string InputPath { get; set; }

            [Option('o', "output", Required = false, HelpText = "Output directory for the packed .S file.")]
            public string OutputPath { get; set; }

            [Option('p', "presets", Required = false, HelpText =
                "Preset file to use instead of the clut_presets.json in the input folder.")]
            public string PresetPath { get; set; }
        }
    }
}
