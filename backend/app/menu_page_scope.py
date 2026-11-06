"""Do not generate menu pages that already exist in Webdev."""
import httpx

from app.project_cache import ProjectCacheError
from app.project_network import Remote


def current_paths(db, site):
    from app.services import _normalized_project_slug
    try:
        with Remote(db, site) as remote:
            project = remote.project()
    except (ProjectCacheError, httpx.HTTPError) as exc:
        raise ValueError("Не удалось проверить существующие страницы в Webdev. Генерация не запущена; повторите после восстановления связи.") from exc
    data = project.get("data") if isinstance(project, dict) else None
    pages = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(pages, list) or any(not isinstance(page, dict) or "slug" not in page for page in pages):
        raise ValueError("Webdev не вернул полный список страниц. Генерация не запущена, чтобы не создать дубли.")
    return {_normalized_project_slug(page["slug"]) for page in pages}
