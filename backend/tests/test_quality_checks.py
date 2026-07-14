from app.services import analyze_content_quality, build_blocks_from_ai_text, extract_ai_article_parts, faq_block, header_block, paragraph_block


def test_quality_check_flags_metadata_and_risky_phrases() -> None:
    payload = {
        "pages": [
            {
                "content": {
                    "blocks": [
                        header_block("Beste Online Casinos", 1),
                        paragraph_block(
                            "Title: Beste Online Casinos Meta Description: text H1: Beste Online Casinos "
                            + ("This payout is garantiert. " * 90)
                        ),
                    ]
                }
            }
        ]
    }

    result = analyze_content_quality(payload)
    codes = {issue["code"] for issue in result["issues"]}

    assert result["status"] == "failed"
    assert "metadata_inside_body" in codes
    assert "risky_phrase" in codes
    assert "oversized_paragraph" in codes


def test_quality_check_accepts_structured_payload() -> None:
    payload = {
        "pages": [
            {
                "content": {
                    "blocks": [
                        header_block("Legale Online Casinos", 1),
                        header_block("GGL-Lizenz und Sicherheit", 2),
                        paragraph_block("Ein Anbieter sollte vor der Einzahlung sorgfältig geprüft werden."),
                        faq_block(
                            [
                                {"question": "Was ist eine GGL-Lizenz?", "answer": "Sie ist ein wichtiger Nachweis."},
                                {"question": "Warum ist KYC wichtig?", "answer": "KYC hilft bei der Identitätsprüfung."},
                                {"question": "Was sollte man prüfen?", "answer": "Lizenz, Limits und Zahlungen."},
                            ]
                        ),
                    ]
                }
            }
        ]
    }

    result = analyze_content_quality(payload)

    assert result["status"] == "ok"
    assert result["issues"] == []


def test_ai_article_parts_and_blocks_keep_structure() -> None:
    text = """Title: Sichere Online Casinos erkennen
Meta Description: Kurzer sicherer Überblick.
H1: Sichere Online Casinos erkennen

Intro:
Ein kurzer Einstieg.

H2: Überblick / schneller Vergleich
| Kriterium | Worauf achten | Warum wichtig |
|---|---|---|
| Lizenz | GGL prüfen | Rechtlicher Rahmen |

H2: Häufige Fehler
- Lizenz nicht prüfen
- Limits ignorieren

Editor Check:
- Struktur: OK
"""

    parts = extract_ai_article_parts(text, "Fallback")
    blocks = build_blocks_from_ai_text(parts["body"], parts["h1"], shortcode=None, include_toc=True, include_faq=False)
    block_types = [block["type"] for block in blocks]

    assert parts["title"] == "Sichere Online Casinos erkennen"
    assert parts["meta_description"] == "Kurzer sicherer Überblick."
    assert "Editor Check" not in parts["body"]
    assert parts["editor_check"] == "- Struktur: OK"
    assert "table" in block_types
    assert "list" in block_types
    assert sum(1 for block in blocks if block["type"] == "header") >= 3


def test_plain_short_lines_do_not_become_headings() -> None:
    text = """Kurzer Einstieg
Das ist ein normaler Absatz.

H2: Echter Abschnitt
Ein weiterer Absatz."""

    blocks = build_blocks_from_ai_text(text, "Test H1", shortcode=None, include_toc=True, include_faq=False)
    headings = [block["data"]["text"] for block in blocks if block["type"] == "header"]

    assert headings == ["Test H1", "Echter Abschnitt"]
