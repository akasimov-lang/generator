"""Add the universal Casinos item to every project menu library.

Revision ID: 0035_casinos_menu_library
Revises: 0034_generation_modes
Create Date: 2026-09-01
"""

from alembic import op


revision = "0035_casinos_menu_library"
down_revision = "0034_generation_modes"
branch_labels = None
depends_on = None


CASINOS_ITEM = """{"name":"Casinos","path":"/casinos/","external_id":"casinos","russian_name":"Казино","description":"Используется для обзоров казино"}"""


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE sites
        SET menu_library = CASE
            WHEN menu_library IS NULL OR json_typeof(menu_library) <> 'array'
                THEN '[{CASINOS_ITEM}]'::json
            ELSE (menu_library::jsonb || '[{CASINOS_ITEM}]'::jsonb)::json
        END
        WHERE menu_library IS NULL
           OR json_typeof(menu_library) <> 'array'
           OR NOT EXISTS (
                SELECT 1
                FROM json_array_elements(menu_library) AS entry
                WHERE lower(COALESCE(entry->>'external_id', '')) = 'casinos'
                   OR lower(COALESCE(entry->>'path', '')) = '/casinos/'
           )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE sites
        SET menu_library = COALESCE((
            SELECT json_agg(entry)
            FROM json_array_elements(menu_library) AS entry
            WHERE NOT (
                lower(COALESCE(entry->>'external_id', '')) = 'casinos'
                AND lower(COALESCE(entry->>'path', '')) = '/casinos/'
            )
        ), '[]'::json)
        WHERE menu_library IS NOT NULL
          AND json_typeof(menu_library) = 'array'
        """
    )
