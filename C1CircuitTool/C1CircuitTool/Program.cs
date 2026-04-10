using CommandLine;
using System;
using System.IO;

namespace C1CircuitTool
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.WriteLine("C1 Circuit Tool - by chmcl95");
            Console.WriteLine();

            Parser.Default.ParseArguments<UnpackVerbs, PackVerbs>(args)
                .WithParsed<UnpackVerbs>(Unpack)
                .WithParsed<PackVerbs>(Pack);
        }

        public static void Unpack(UnpackVerbs options)
        {
            if (!File.Exists(options.InputPath))
            {
                Console.WriteLine($"Provided '{options.InputPath}' does not exist.");
                return;
            }
            string outputPath = options.OutputPath;
            if (string.IsNullOrEmpty(options.OutputPath))
            {
                outputPath = $"{Path.GetDirectoryName(options.InputPath)}\\extracted";
            }

            Unpacker unpacker = new Unpacker(options.InputPath, outputPath);
            unpacker.Unpack();

            return;
        }

        public static void Pack(PackVerbs options)
        {
            if (!Directory.Exists(options.InputPath))
            {
                Console.WriteLine($"Provided '{options.InputPath}' does not exist.");
                return;
            }

            string outputPath = options.OutputPath;
            if (string.IsNullOrEmpty(options.OutputPath))
            {
                outputPath = $"{Path.GetDirectoryName(options.InputPath)}\\packed";
            }

            Packer packer = new Packer(options.InputPath, outputPath);
            packer.Pack();

            return;
        }

        [Verb("unpack", HelpText = "Unpacks .S files are extract in \"extracted\" folder.(Deafult)")]
        public class UnpackVerbs
        {
            [Option('i', "input", Required = true, HelpText = "Input .S file like ALLCAR.S.")]
            public string InputPath { get; set; }

            [Option('o', "output", Required = false, HelpText = "Output directory for the extracted files.")]
            public string OutputPath { get; set; }

        }

        [Verb("pack", HelpText = "Packing extrackted S file. Files are generat in \"patched\" folder.(Deafult)")]
        public class PackVerbs
        {
            [Option('i', "input", Required = true, HelpText = "Input Directry. Need extracted R5.ALL files.")]
            public string InputPath { get; set; }

            [Option('o', "output", Required = false, HelpText = "Output directory for the patched files.")]
            public string OutputPath { get; set; }

        }
    }
}
