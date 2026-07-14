from app.services import analyze_content_quality, faq_block, header_block, paragraph_block


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
