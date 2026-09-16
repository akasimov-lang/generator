"""Editable preset of language-region codes; country lists verified 2026-09-16.

EU: https://european-union.europa.eu/principles-countries-history/eu-countries_en
CIS portal country directory: https://e-cis.info/ (includes MD and UA).
This is a geographic preset, not a statement about treaty participation.
"""
COUNTRY_LANGUAGES = {
    "AT": ["de"], "BE": ["nl", "fr", "de"], "BG": ["bg"], "HR": ["hr"],
    "CY": ["el", "tr"], "CZ": ["cs"], "DK": ["da"], "EE": ["et"],
    "FI": ["fi", "sv"], "FR": ["fr"], "DE": ["de"], "GR": ["el"],
    "HU": ["hu"], "IE": ["ga", "en"], "IT": ["it"], "LV": ["lv"],
    "LT": ["lt"], "LU": ["lb", "fr", "de"], "MT": ["mt", "en"],
    "NL": ["nl"], "PL": ["pl"], "PT": ["pt"], "RO": ["ro"], "SK": ["sk"],
    "SI": ["sl"], "ES": ["es"], "SE": ["sv"],
    "AZ": ["az"], "AM": ["hy"], "BY": ["be", "ru"], "KZ": ["kk", "ru"],
    "KG": ["ky", "ru"], "MD": ["ro"], "RU": ["ru"], "TJ": ["tg"],
    "TM": ["tk"], "UZ": ["uz"], "UA": ["uk"],
}


def default_language_pool():
    return [f"{language}-{country}" for country, languages in COUNTRY_LANGUAGES.items() for language in languages]
