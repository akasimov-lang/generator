"""Release inactive archived drafts' URLs without changing their content/history.

The reservation flag is maintained by PostgreSQL for both task and item changes,
including a worker finishing generation after the task has been archived.
"""
from alembic import op

revision = "0069_archived_content_urls"
down_revision = "0068_mass_reglue_participation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE content_items ADD COLUMN IF NOT EXISTS archived_url_released BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("""
        CREATE OR REPLACE FUNCTION content_archived_url_released(c content_items, t generation_tasks)
        RETURNS boolean LANGUAGE sql STABLE AS $$
            SELECT COALESCE(
                t.archived_at IS NOT NULL
                AND t.status NOT IN ('generating', 'generation_queued', 'publishing', 'scheduled')
                AND c.status IN ('draft', 'generated', 'approved', 'generation_failed', 'system_stopped')
                AND NOT (t.auto_publish AND c.status IN ('generated', 'approved'))
                AND c.published_at IS NULL AND COALESCE(c.published_url, '') = ''
                AND c.last_publication_status_code IS NULL AND c.publication_campaign_id IS NULL,
                FALSE
            )
        $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION sync_content_archived_url() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            SELECT content_archived_url_released(NEW, t) INTO NEW.archived_url_released
            FROM generation_tasks t WHERE t.id = NEW.task_id;
            NEW.archived_url_released := COALESCE(NEW.archived_url_released, FALSE);
            RETURN NEW;
        END $$
    """)
    op.execute("DROP TRIGGER IF EXISTS sync_content_archived_url ON content_items")
    op.execute("""
        CREATE TRIGGER sync_content_archived_url BEFORE INSERT OR UPDATE ON content_items
        FOR EACH ROW EXECUTE FUNCTION sync_content_archived_url()
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION sync_task_archived_urls() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            UPDATE content_items c SET archived_url_released = content_archived_url_released(c, NEW)
            WHERE c.task_id = NEW.id
              AND c.archived_url_released IS DISTINCT FROM content_archived_url_released(c, NEW);
            RETURN NEW;
        END $$
    """)
    op.execute("DROP TRIGGER IF EXISTS sync_task_archived_urls ON generation_tasks")
    op.execute("""
        CREATE TRIGGER sync_task_archived_urls AFTER UPDATE OF archived_at, status, auto_publish ON generation_tasks
        FOR EACH ROW EXECUTE FUNCTION sync_task_archived_urls()
    """)
    op.execute("""
        UPDATE content_items c SET archived_url_released = content_archived_url_released(c, t)
        FROM generation_tasks t WHERE t.id = c.task_id
          AND c.archived_url_released IS DISTINCT FROM content_archived_url_released(c, t)
    """)
    op.execute("DROP INDEX IF EXISTS uq_content_items_active_site_slug")
    op.execute("""
        CREATE UNIQUE INDEX uq_content_items_active_site_slug ON content_items (site_id, slug)
        WHERE site_id IS NOT NULL AND status <> 'deleted' AND NOT archived_url_released
    """)


def downgrade():
    # Refuse rollback if a released URL has since been reused; never delete history.
    op.execute("DROP INDEX IF EXISTS uq_content_items_active_site_slug")
    op.execute("""
        CREATE UNIQUE INDEX uq_content_items_active_site_slug ON content_items (site_id, slug)
        WHERE site_id IS NOT NULL AND status <> 'deleted'
    """)
    op.execute("DROP TRIGGER IF EXISTS sync_task_archived_urls ON generation_tasks")
    op.execute("DROP TRIGGER IF EXISTS sync_content_archived_url ON content_items")
    op.execute("DROP FUNCTION IF EXISTS sync_task_archived_urls()")
    op.execute("DROP FUNCTION IF EXISTS sync_content_archived_url()")
    op.execute("DROP FUNCTION IF EXISTS content_archived_url_released(content_items, generation_tasks)")
    op.execute("ALTER TABLE content_items DROP COLUMN IF EXISTS archived_url_released")
