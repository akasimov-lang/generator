"""Assign the working v6 prompt to every project.

Revision ID: 0026_default_working_prompt
Revises: 0025_content_section_mode
Create Date: 2026-08-25
"""

from alembic import op


revision = "0026_default_working_prompt"
down_revision = "0025_content_section_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE prompt_templates SET name = 'Промпт рабочий' "
        "WHERE name IN ('Промт рабочий', 'Промпт тест 1 v6')"
    )
    op.execute(
        "UPDATE generation_tasks SET prompt_template_name = 'Промпт рабочий' "
        "WHERE prompt_template_name IN ('Промт рабочий', 'Промпт тест 1 v6')"
    )
    op.execute(
        "UPDATE content_items SET generation_prompt_name = 'Промпт рабочий' "
        "WHERE generation_prompt_name IN ('Промт рабочий', 'Промпт тест 1 v6')"
    )
    op.execute(
        "UPDATE sites "
        "SET default_prompt_template_id = ("
        "SELECT id FROM prompt_templates "
        "WHERE name = 'Промпт рабочий' "
        "ORDER BY created_at DESC, updated_at DESC LIMIT 1"
        ") "
        "WHERE EXISTS ("
        "SELECT 1 FROM prompt_templates WHERE name = 'Промпт рабочий'"
        ")"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE prompt_templates SET name = 'Промт рабочий' "
        "WHERE name = 'Промпт рабочий'"
    )
    op.execute(
        "UPDATE generation_tasks SET prompt_template_name = 'Промт рабочий' "
        "WHERE prompt_template_name = 'Промпт рабочий'"
    )
    op.execute(
        "UPDATE content_items SET generation_prompt_name = 'Промт рабочий' "
        "WHERE generation_prompt_name = 'Промпт рабочий'"
    )
