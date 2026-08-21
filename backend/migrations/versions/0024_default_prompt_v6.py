"""Use prompt version 6 as the default for every project.

Revision ID: 0024_default_prompt_v6
Revises: 0023_campaign_completed
Create Date: 2026-08-21
"""

from alembic import op


revision = "0024_default_prompt_v6"
down_revision = "0023_campaign_completed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE prompt_templates SET name = 'Промт рабочий' "
        "WHERE name = 'Промпт тест 1 v6'"
    )
    op.execute(
        "UPDATE generation_tasks SET prompt_template_name = 'Промт рабочий' "
        "WHERE prompt_template_name = 'Промпт тест 1 v6'"
    )
    op.execute(
        "UPDATE content_items SET generation_prompt_name = 'Промт рабочий' "
        "WHERE generation_prompt_name = 'Промпт тест 1 v6'"
    )
    op.execute(
        "UPDATE sites "
        "SET default_prompt_template_id = ("
        "SELECT id FROM prompt_templates "
        "WHERE name = 'Промт рабочий' "
        "ORDER BY created_at DESC, updated_at DESC LIMIT 1"
        ") "
        "WHERE EXISTS ("
        "SELECT 1 FROM prompt_templates WHERE name = 'Промт рабочий'"
        ")"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE prompt_templates SET name = 'Промпт тест 1 v6' "
        "WHERE name = 'Промт рабочий'"
    )
    op.execute(
        "UPDATE generation_tasks SET prompt_template_name = 'Промпт тест 1 v6' "
        "WHERE prompt_template_name = 'Промт рабочий'"
    )
    op.execute(
        "UPDATE content_items SET generation_prompt_name = 'Промпт тест 1 v6' "
        "WHERE generation_prompt_name = 'Промт рабочий'"
    )
