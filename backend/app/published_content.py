"""Visible article text metrics, excluding metadata and EditorJS settings."""
import re
from html import unescape


def article_words(payload: dict) -> int:
    chunks = []

    def append(value):
        if isinstance(value, str):
            chunks.append(value)
        elif isinstance(value, list):
            for entry in value:
                append(entry)
        elif isinstance(value, dict):
            for key in ("content", "text", "items"):
                if key in value:
                    append(value[key])

    for page in payload.get("pages") or []:
        for block in (page.get("content") or {}).get("blocks") or []:
            data = block.get("data") or {}
            kind = block.get("type")
            if kind in {"header", "paragraph"} and isinstance(data, dict):
                append(data.get("text"))
            elif kind == "list" and isinstance(data, dict):
                append(data.get("items"))
            elif kind == "table" and isinstance(data, dict):
                append(data.get("content"))
            elif kind == "quote" and isinstance(data, dict):
                append(data.get("quote") or data.get("text"))
                append(data.get("caption"))
            elif kind == "faq":
                for entry in data if isinstance(data, list) else data.get("items", []):
                    if isinstance(entry, dict):
                        append(entry.get("question"))
                        append(entry.get("answer"))
            elif kind == "plusMinus" and isinstance(data, dict):
                for entry in data.get("values", []):
                    append(entry.get("plus"))
                    append(entry.get("minus"))
    text = re.sub(r"<(?:br\b[^>]*|/(?:p|div|li))>", " ", " ".join(chunks), flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return len(re.findall(r"\b[\w'-]+\b", unescape(text), flags=re.UNICODE))
