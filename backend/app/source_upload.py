"""Extract HTML source stored as text in Word documents."""
import io
import subprocess
import tempfile
import zipfile
from xml.etree import ElementTree

MAX_UPLOAD = 2_000_000
MAX_DOCUMENT_XML = 10_000_000
WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_source_document(data: bytes, extension: str) -> str:
    if not data:
        raise ValueError("Файл пуст. Выберите HTML главной страницы.")
    if len(data) > MAX_UPLOAD:
        raise ValueError("Файл превышает 2 МБ. Выберите файл меньшего размера.")
    if extension == "docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                info = archive.getinfo("word/document.xml")
                if info.file_size > MAX_DOCUMENT_XML:
                    raise ValueError("Содержимое документа слишком большое.")
                xml = archive.read(info)
            if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
                raise ValueError("Неподдерживаемый XML в документе.")
            root = ElementTree.fromstring(xml)
            paragraphs = []
            for paragraph in root.iter(WORD + "p"):
                paragraphs.append("".join(
                    node.text or "" if node.tag == WORD + "t" else
                    "\t" if node.tag == WORD + "tab" else "\n"
                    for node in paragraph.iter()
                    if node.tag in {WORD + "t", WORD + "tab", WORD + "br", WORD + "cr"}
                ))
            text = "\n".join(paragraphs)
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError, RuntimeError, NotImplementedError) as exc:
            raise ValueError("Не удалось прочитать DOCX. Проверьте файл или сохраните HTML в TXT.") from exc
    elif extension == "doc":
        if not data.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
            raise ValueError("Не удалось прочитать DOC. Сохраните документ как DOCX или TXT.")
        try:
            with tempfile.NamedTemporaryFile(suffix=".doc") as document:
                document.write(data)
                document.flush()
                result = subprocess.run(
                    ["antiword", "-m", "UTF-8.txt", "-w", "0", document.name],
                    capture_output=True, timeout=15, check=True,
                )
            text = result.stdout.decode("utf-8")
        except FileNotFoundError as exc:
            raise ValueError("Чтение DOC недоступно на сервере. Сохраните документ как DOCX или TXT.") from exc
        except (subprocess.SubprocessError, UnicodeError) as exc:
            raise ValueError("Не удалось прочитать DOC. Проверьте файл или сохраните HTML в TXT.") from exc
    else:
        raise ValueError("Выберите файл DOC или DOCX.")
    if not text.strip():
        raise ValueError("Документ пуст. Вставьте в него HTML главной страницы.")
    if len(text.encode("utf-8")) > MAX_UPLOAD:
        raise ValueError("HTML превышает 2 МБ.")
    return text
