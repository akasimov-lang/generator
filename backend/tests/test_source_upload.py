import io
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

from app.source_upload import extract_source_document


def docx(xml):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml)
    return output.getvalue()


class SourceUploadTests(unittest.TestCase):
    def test_docx_preserves_html_and_paragraphs(self):
        data = docx('''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
        <w:p><w:r><w:t>&lt;html&gt;Привет &amp; </w:t></w:r><w:r><w:t>мир&lt;/html&gt;</w:t></w:r></w:p>
        <w:p><w:r><w:t>next</w:t><w:tab/><w:t>line</w:t><w:br/><w:t>end</w:t></w:r></w:p>
        </w:body></w:document>''')
        self.assertEqual(extract_source_document(data, "docx"), '<html>Привет & мир</html>\nnext\tline\nend')

    def test_invalid_upload(self):
        for data, extension in [(b"", "docx"), (b"broken", "docx"), (b"broken", "doc"), (b"x" * 2_000_001, "docx")]:
            with self.subTest(extension=extension, size=len(data)), self.assertRaises(ValueError):
                extract_source_document(data, extension)

    def test_docx_expansion_limit(self):
        with self.assertRaisesRegex(ValueError, "слишком большое"):
            extract_source_document(docx(b"x" * 10_000_001), "docx")

    def test_doc_uses_utf8_without_line_wrapping(self):
        with patch("app.source_upload.subprocess.run", return_value=SimpleNamespace(stdout='<html>Привет</html>'.encode())) as run:
            self.assertEqual(extract_source_document(bytes.fromhex("d0cf11e0a1b11ae1"), "doc"), '<html>Привет</html>')
            self.assertEqual(run.call_args.args[0][:5], ["antiword", "-m", "UTF-8.txt", "-w", "0"])
            self.assertEqual(run.call_args.kwargs["timeout"], 15)

    def test_doc_converter_missing(self):
        with patch("app.source_upload.subprocess.run", side_effect=FileNotFoundError), self.assertRaisesRegex(ValueError, "недоступно"):
            extract_source_document(bytes.fromhex("d0cf11e0a1b11ae1"), "doc")
