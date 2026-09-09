from app.services import analyze_content_quality, build_blocks_from_ai_text, concise_h1_from_topic, extract_ai_article_parts, faq_block, header_block, normalize_editor_inline_markup, paragraph_block, seo_title_needs_improvement


def test_seo_title_requires_at_least_80_characters_and_seven_words() -> None:
    assert seo_title_needs_improvement("Kryptowaluty")
    assert seo_title_needs_improvement("Kryptowaluty w kasynach online: bezpieczne wpłaty i wypłaty środków")
    assert not seo_title_needs_improvement(
        "Kryptowaluty w kasynach online: jak działają bezpieczne wpłaty, wypłaty i ochrona środków gracza"
    )


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


def test_markdown_bold_is_converted_to_html_in_generated_and_legacy_blocks() -> None:
    blocks = build_blocks_from_ai_text(
        "- **Identifier les plaintes structurelles** : vérifier les retards\n- __Analyser le support__ : comparer les réponses",
        "Notes et avis",
        shortcode=None,
        include_toc=False,
        include_faq=False,
    )
    assert blocks[1]["data"]["items"] == [
        "<strong>Identifier les plaintes structurelles</strong> : vérifier les retards",
        "<strong>Analyser le support</strong> : comparer les réponses",
    ]

    legacy = normalize_editor_inline_markup({
        "pages": [{"content": {"blocks": [
            {"type": "paragraph", "data": {"text": "Texte avec **mise en évidence**."}},
            {"type": "faq", "data": [{"question": "**Question**", "answer": "__Réponse__"}]},
        ]}}],
    })
    assert legacy["pages"][0]["content"]["blocks"][0]["data"]["text"] == "Texte avec <strong>mise en évidence</strong>."
    assert legacy["pages"][0]["content"]["blocks"][1]["data"][0] == {
        "question": "<strong>Question</strong>",
        "answer": "<strong>Réponse</strong>",
    }


def test_inline_faq_paragraphs_are_converted_to_editor_faq_block() -> None:
    payload = normalize_editor_inline_markup({
        "pages": [{"content": {"blocks": [
            {"id": "faq-title", "type": "header", "data": {"text": "FAQ", "level": 2}},
            {"id": "part-one", "type": "paragraph", "data": {"text": "Q: Первый вопрос? A: Первый ответ."}},
            {"id": "part-two", "type": "paragraph", "data": {"text": "Q: Второй вопрос?"}},
            {"id": "part-three", "type": "paragraph", "data": {"text": "A: Второй ответ с **важной частью**."}},
            {"id": "next-title", "type": "header", "data": {"text": "Следующий раздел", "level": 2}},
            {"id": "next-text", "type": "paragraph", "data": {"text": "Текст раздела."}},
        ]}}],
    })

    blocks = payload["pages"][0]["content"]["blocks"]
    assert [block["type"] for block in blocks] == ["header", "faq", "header", "paragraph"]
    assert isinstance(blocks[1]["id"], str) and blocks[1]["id"]
    assert blocks[1]["data"] == [
        {"question": "Первый вопрос?", "answer": "Первый ответ."},
        {"question": "Второй вопрос?", "answer": "Второй ответ с <strong>важной частью</strong>."},
    ]
    assert blocks[2]["id"] == "next-title"
    assert blocks[3]["data"]["text"] == "Текст раздела."


def test_legacy_faq_object_is_normalized_to_question_answer_array() -> None:
    payload = normalize_editor_inline_markup({
        "pages": [{"content": {"blocks": [{
            "type": "faq",
            "data": {"items": [{"q": "Is it available?", "a": "Yes.", "open": True}]},
        }]}}],
    })

    faq = payload["pages"][0]["content"]["blocks"][0]
    assert faq["type"] == "faq"
    assert isinstance(faq["id"], str) and faq["id"]
    assert faq["data"] == [{"question": "Is it available?", "answer": "Yes."}]


def test_faq_word_inside_regular_paragraph_does_not_change_block_structure() -> None:
    source = {"pages": [{"content": {"blocks": [
        {"id": "body", "type": "paragraph", "data": {"text": "Читайте FAQ перед обращением."}},
    ]}}]}

    assert normalize_editor_inline_markup(source) == source


def test_generated_q_and_a_section_uses_editor_faq_contract() -> None:
    blocks = build_blocks_from_ai_text(
        "H2: FAQ\nQ: Can I register?\nA: Yes.\nQ: Is verification required?\nA: It may be required.\nH2: Final notes\nKeep your details current.",
        "Test page",
        shortcode=None,
        include_toc=False,
        include_faq=True,
    )

    faq = next(block for block in blocks if block["type"] == "faq")
    assert faq["data"] == [
        {"question": "Can I register?", "answer": "Yes."},
        {"question": "Is verification required?", "answer": "It may be required."},
    ]
    assert any(block["type"] == "header" and block["data"]["text"] == "Final notes" for block in blocks)


def test_faq_is_always_normalized_to_receiver_format() -> None:
    payload = normalize_editor_inline_markup({
        "pages": [{"content": {"blocks": [{
            "type": "faq",
            "data": {"items": [
                {"question": "Есть ли приложение?", "answer": "Да.", "extra": "remove"},
                {"question": "**Как войти?**", "answer": "Через __официальный сайт__."},
            ]},
            "legacy": True,
        }]}}],
    })

    faq = payload["pages"][0]["content"]["blocks"][0]
    assert set(faq) == {"id", "type", "data"}
    assert len(faq["id"]) == 10
    assert faq["type"] == "faq"
    assert faq["data"] == [
        {"question": "Есть ли приложение?", "answer": "Да."},
        {"question": "<strong>Как войти?</strong>", "answer": "Через <strong>официальный сайт</strong>."},
    ]


def test_concise_h1_uses_primary_topic_part_and_preserves_title_case() -> None:
    topic = "Beste Online Casinos in Deutschland 2026: Legale Anbieter im Vergleich"

    assert concise_h1_from_topic(topic) == "Beste Online Casinos in Deutschland 2026"
    assert concise_h1_from_topic("Legale Anbieter mit GGL-Lizenz") == "Legale Anbieter mit GGL-Lizenz"
