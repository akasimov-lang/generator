"""Retarget literal old-Main alternate URLs while preserving template variables."""
import re
from urllib.parse import urlsplit


def retarget_main_alternates(state, new_main):
    old_main = str(state.get('canon') or '').lower()
    markup = state.get('alternateMarkup') or ''
    attribute = re.compile(r'''\b([\w-]+)\s*=\s*(["'])(.*?)\2''', re.DOTALL)

    def replace_link(match):
        tag = match.group(0)
        attrs = {a.group(1).lower(): a for a in attribute.finditer(tag)}
        if 'href' not in attrs or 'rel' not in attrs or 'alternate' not in attrs['rel'].group(3).lower().split():
            return tag
        href = attrs['href']
        value = href.group(3)
        try:
            url = urlsplit(value)
            if (url.scheme.lower() not in {'', 'http', 'https'} or not url.netloc
                    or url.username or url.password or '{{' in url.netloc
                    or (url.hostname or '').lower() != old_main):
                return tag
        except ValueError:
            return tag
        # Preserve protocol, path, query, fragments, quoting and all other attributes.
        start = value.index('//') + 2
        updated = value[:start] + new_main + value[start + len(url.hostname):]
        return tag[:href.start(3)] + updated + tag[href.end(3):]

    updated = re.sub(r'<link\b[^>]*>', replace_link, markup, flags=re.IGNORECASE)
    return {'alternateMarkup': updated} if updated != markup else {}
