"""Deterministic localized base keywords for explicitly selected general projects."""
import re

BEST_CASINOS = {
    'pl': 'najlepsze kasyna', 'en': 'best casinos', 'de': 'beste Casinos',
    'cs': 'nejlepší kasina', 'da': 'bedste casinoer', 'sv': 'bästa casinon',
    'bg': 'най-добрите казина', 'ro': 'cele mai bune cazinouri', 'nl': 'beste casino’s',
    'es': 'mejores casinos', 'fr': 'meilleurs casinos', 'it': 'migliori casinò',
    'pt': 'melhores casinos', 'fi': 'parhaat kasinot', 'et': 'parimad kasiinod',
    'lv': 'labākie kazino', 'sl': 'najboljše igralnice', 'hu': 'legjobb kaszinók',
    'ga': 'na ceasaíneonna is fearr',
}


def additions(geo, language):
    country = re.split('[-_]', (geo or '').strip().lower())[-1]
    country = {'sv': 'se', 'cs': 'cz'}.get(country, country)
    if not re.fullmatch('[a-z]{2}', country):
        raise ValueError('Не удалось определить короткий код GEO.')
    lang = re.split('[-_]', (language or '').strip().lower())[0]
    lang = {'cz': 'cs', 'dk': 'da', 'se': 'sv', 'au': 'en'}.get(lang, lang)
    if lang not in BEST_CASINOS:
        raise ValueError('Нет проверенного перевода для языка ' + lang)
    return ['online casino', 'casino ' + country, BEST_CASINOS[lang]]
