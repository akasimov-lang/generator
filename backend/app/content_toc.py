"""Portable Editor.js contents links: targets live in heading HTML, not renderer-specific fields."""
from copy import deepcopy
from html import escape, unescape
import re


def plain(value):
    return ' '.join(unescape(re.sub(r'<[^>]*>', '', str(value or ''))).split())


def normalize_toc_blocks(blocks):
    result = deepcopy(blocks)
    toc = [b for b in result if isinstance(b, dict) and (b.get('type') == 'toc' or b.get('pagepilot_toc') is True)]
    if not toc:
        return result
    used = set()
    for block in result:
        if isinstance(block, dict):
            used.update(re.findall(r'\bid=["\']([^"\']+)', str(block.get('data') or {})))
    headings = []
    assigned = set()
    for index, block in enumerate(result):
        if not isinstance(block, dict) or block.get('type') != 'header' or not isinstance(block.get('data'), dict):
            continue
        data = block['data']; text = str(data.get('text') or '')
        label = plain(text)
        if not label:
            continue
        target = re.search(r'<span\s+id="(pp-section-[a-zA-Z0-9_-]+)"\s*></span>', text)
        if target and target.group(1) not in assigned:
            anchor = target.group(1)
        else:
            if target:
                text = text[:target.start()] + text[target.end():]
            base = 'pp-section-' + (re.sub(r'[^a-zA-Z0-9_-]', '', str(block.get('id') or '')) or str(index))
            anchor = base; suffix = 2
            while anchor in used:
                anchor = base + '-' + str(suffix); suffix += 1
            used.add(anchor)
            data['text'] = '<span id="' + anchor + '"></span>' + text
        assigned.add(anchor)
        headings.append((anchor, label))
    for block in toc:
        block['type'] = 'list'
        block['pagepilot_toc'] = True
        block['data'] = {'style': 'unordered', 'items': [
            '<a href="#' + anchor + '">' + escape(label) + '</a>' for anchor, label in headings]}
    return [b for b in result if b not in toc or headings]
