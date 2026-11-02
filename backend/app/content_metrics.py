"""Measured changes against the previous saved page; no external plagiarism claim."""
from difflib import SequenceMatcher
from functools import lru_cache
import hashlib
import math
import re
import unicodedata

from app.page_word_count import page_visible_text

WORD = re.compile(r"\b[\w]+(?:['’\-][\w]+)*\b", re.UNICODE)


def normalized_words(text):
    return tuple(WORD.findall(unicodedata.normalize('NFKC', text).casefold()))


def brand_term(brand):
    if str(brand or '').strip().casefold() == 'общие ключи':
        return ''
    return ' '.join(re.sub(r'\bcasino\b', '', str(brand or ''), flags=re.I).strip(' -–—').split())


def counts(page, brand=''):
    text = page_visible_text(page)
    if text is None:
        return {}
    words = normalized_words(text)
    term = brand_term(brand)
    pattern = r'(?<!\w)' + r'[\s\-]+'.join(re.escape(word) for word in term.split()) + r'(?!\w)'
    return {'unique_words': len(set(words)),
            'brand_mentions': len(re.findall(pattern, unicodedata.normalize('NFKC', text), re.I)) if term else None}


@lru_cache(maxsize=64)
def changed_percent(before, after):
    if not after:
        return None
    matches = sum(block.size for block in SequenceMatcher(None, before, after, autojunk=False).get_matching_blocks())
    return math.floor(100 * (len(after) - matches) / len(after) + .5)


def comparison(before, after):
    old, new = page_visible_text(before), page_visible_text(after)
    if old is None or new is None:
        return {}
    old_words, new_words = normalized_words(old), normalized_words(new)
    reduction = math.floor(100 * (len(old_words) - len(new_words)) / len(old_words) + .5) if old_words and len(new_words) < len(old_words) else 0
    return {'uniqueness_percent': changed_percent(old_words, new_words),
            'shortened_percent': reduction,
            'uniqueness_basis': 'previous_saved_text'}


def target_percent(group_id, site_id):
    """Persistable varied target, stable when the same task is retried."""
    digest = hashlib.sha256((str(group_id) + ':' + str(site_id)).encode()).digest()
    return 30 + int.from_bytes(digest[:8], 'big') % 61
