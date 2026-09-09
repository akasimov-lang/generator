"""Canonicalize FAQ blocks in saved generated content.

Revision ID: 0041_canonical_faq_blocks
Revises: 0040_section_review
Create Date: 2026-09-09
"""

import copy
import uuid

from alembic import op
import sqlalchemy as sa


revision = "0041_canonical_faq_blocks"
down_revision = "0040_section_review"
branch_labels = None
depends_on = None


def _canonicalize(payload: object) -> tuple[object, bool]:
    if not isinstance(payload, dict):
        return payload, False
    result = copy.deepcopy(payload)
    changed = False
    for page in result.get("pages", []):
        if not isinstance(page, dict):
            continue
        content = page.get("content")
        blocks = content.get("blocks") if isinstance(content, dict) else []
        for block in blocks if isinstance(blocks, list) else []:
            if not isinstance(block, dict) or block.get("type") != "faq":
                continue
            data = block.get("data")
            items = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []
            canonical = [
                {
                    "question": str(item.get("question") or ""),
                    "answer": str(item.get("answer") or ""),
                }
                for item in items
                if isinstance(item, dict)
            ]
            block_id = str(block.get("id") or uuid.uuid4().hex[:10])
            if block.get("id") != block_id or data != canonical or set(block) != {"id", "type", "data"}:
                block.clear()
                block.update({"id": block_id, "type": "faq", "data": canonical})
                changed = True
    return result, changed


def upgrade() -> None:
    connection = op.get_bind()
    content_items = sa.table(
        "content_items",
        sa.column("id", sa.String()),
        sa.column("generated_json", sa.JSON()),
    )
    rows = connection.execute(sa.select(content_items.c.id, content_items.c.generated_json)).all()
    for row in rows:
        normalized, changed = _canonicalize(row.generated_json)
        if changed:
            connection.execute(
                content_items.update().where(content_items.c.id == row.id).values(generated_json=normalized)
            )


def downgrade() -> None:
    # The canonical representation is also understood by older application versions.
    pass
