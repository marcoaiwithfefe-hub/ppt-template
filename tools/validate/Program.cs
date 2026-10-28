// C5: Open XML SDK validation (Office 2016 format) of .pptx files.
// Usage: dotnet run --project tools/validate -- <file.pptx> [...]
// Prints one JSON line per file: {"file", "errors": [{"id", "description", "part", "path"}]}.
using System.Text.Json;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Validation;

var validator = new OpenXmlValidator(FileFormatVersions.Office2016);
var exit = 0;
foreach (var file in args)
{
    var errors = new List<object>();
    try
    {
        using var doc = PresentationDocument.Open(file, false);
        foreach (var e in validator.Validate(doc))
        {
            errors.Add(new { id = e.Id, description = e.Description, part = e.Part?.Uri.ToString(), path = e.Path?.XPath });
        }
    }
    catch (Exception ex)
    {
        errors.Add(new { id = "open-failed", description = ex.Message, part = (string?)null, path = (string?)null });
    }
    if (errors.Count > 0) exit = 1;
    Console.WriteLine(JsonSerializer.Serialize(new { file, errors }));
}
return exit;
