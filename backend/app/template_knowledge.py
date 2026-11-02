"""Brand/GEO competitor knowledge, copied into each template as a source snapshot."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unicodedata

from sqlalchemy import select

from app import models
from app.template_sources import excerpt

LIBRARY = Path(__file__).parent / "data" / "template_knowledge"


def source_excerpt(source):
    result = excerpt(source.google_html)
    if not (source.capture or {}).get("knowledge_id"):
        return result

    class ReadableHTML(HTMLParser):
        def __init__(self):
            super().__init__()
            self.hidden = 0
            self.parts = []

        def handle_starttag(self, tag, attrs):
            if tag in {"script", "style", "noscript", "template"}:
                self.hidden += 1

        def handle_endtag(self, tag):
            if tag in {"script", "style", "noscript", "template"}:
                self.hidden = max(0, self.hidden - 1)
            if not self.hidden and tag in {"p", "li", "tr", "h1", "h2", "h3", "section"}:
                self.parts.append("\n")

        def handle_data(self, data):
            if not self.hidden and data.strip():
                self.parts.append(" ".join(data.split()))

    parser = ReadableHTML()
    parser.feed(source.google_html)
    text = "\n".join(line.strip() for line in " ".join(parser.parts).splitlines() if line.strip())
    return {**result, "excerpt": text[:12000], "excerpt_truncated": len(text) > 12000,
            **({'site_structure': source.capture['site_structure']} if source.capture.get('site_structure') else {})}


def brand_key(value):
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", value).casefold())


def matching_sources(brand, geo):
    entries = json.loads((LIBRARY / "index.json").read_text(encoding="utf-8"))
    return [entry for entry in entries if brand_key(entry["brand"]) == brand_key(brand)
            and entry["geo"].upper() == geo.upper()]


def attach_sources(db, row):
    """Preserve imported HTML and provenance; never overwrite a manually edited snapshot."""
    from app.template_knowledge_library import entries as library_entries
    entries = library_entries(db, row.brand, row.geo, html=True)
    if not entries:
        return
    sources = db.scalars(select(models.TemplateSource).where(
        models.TemplateSource.template_id == row.id)).all()
    research = dict((row.document or {}).get("research") or {})
    items = list(research.get("sources") or [])
    changed = False
    for entry in entries:
        source = next((s for s in sources if (s.capture or {}).get("knowledge_id") == entry["id"]), None)
        if source is None:
            # An explicitly supplied copy of the same competitor takes precedence.
            source = next((s for s in sources if entry["url"] and s.url.rstrip("/") == entry["url"].rstrip("/") and not (s.capture or {}).get('knowledge_id') and s.google_html), None)
        if source is None:
            source = next((s for s in sources if (not (s.capture or {}).get('knowledge_id') or (s.capture or {}).get('source')=='manual_html') and s.google_html
                           and hashlib.sha256(s.google_html.encode('utf-8')).hexdigest()==entry['sha256']),None)
        if source is None:
            if len(sources) >= 10:
                continue
            html = entry['html']
            digest = hashlib.sha256(html.encode("utf-8")).hexdigest()
            if digest != entry["sha256"]:
                raise ValueError("Повреждён HTML конкурента в базе знаний")
            excerpt(html)  # Reject empty HTML or challenge pages before saving a snapshot.
            source = models.TemplateSource(template_id=row.id, url=entry["url"], google_html=html,
                capture={"source": "user_upload", "status": "google_ready", "revision": 0,
                    "knowledge_id": entry["id"], "brand": entry["brand"], "geo": entry["geo"],
                    "added_at": entry["added_at"], "sha256": digest, "filename": entry["filename"],
                    "site_structure": entry.get('structure') or {},
                    "note": "HTML конкурента предоставлен пользователем; не результат проверки Google."})
            db.add(source)
            db.flush()
            sources.append(source)
        if (source.capture or {}).get('knowledge_id') == entry['id'] and source.capture.get('site_structure', {}) != entry.get('structure', {}):
            source.capture = {**source.capture, 'site_structure': entry.get('structure') or {}}
            changed = True
        existing = next((item for item in items if item.get("source_id") == source.id
                         or (source.url and not item.get('knowledge_id') and item.get("url", "").rstrip("/") == source.url.rstrip("/"))), None)
        if existing and existing.get("source_id") == source.id:
            continue
        if existing:
            items.remove(existing)
        items.insert(0, {"url": source.url, "title": entry["title"], "source_id": source.id,
                         "origin": "knowledge_base", "knowledge_id": entry["id"]})
        changed = True
    if changed:
        for position, item in enumerate(items, 1):
            items[position - 1] = {**item, "position": position}
        row.document = {**(row.document or {}), "research": {
            "search_complete": False, **research, "sources": items, "analysis": None}}
