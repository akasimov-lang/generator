"""Versioned project templates imported from user-provided CSV files."""
import json
from pathlib import Path


def template_catalog() -> list[dict]:
    return json.loads((Path(__file__).parent / 'data' / 'alternate_templates.json').read_text())['profiles']

