# Deploy

Production deploy идет через git push на сервер.

## Remote

```bash
git remote add production seotech-web-autocontent:/home/akasimov/generator.git
```

В этом проекте SSH удобнее запускать через local config:

```bash
ssh -F .ssh/config seotech-web-autocontent
```

## Deploy

```bash
git push production main
```

На сервере настроен bare repository:

- repo: `/home/akasimov/generator.git`
- worktree: `/home/akasimov/generator`
- deploy hook: `/home/akasimov/generator.git/hooks/post-receive`

Hook после push:

1. Checkout `main` в `/home/akasimov/generator`.
2. Проверяет наличие `.env`.
3. Собирает backend image.
4. Поднимает `postgres` и `redis`.
5. Запускает `alembic upgrade head`.
6. Запускает `docker-compose up -d --build`.
7. Перезапускает `nginx`, чтобы он заново резолвил Docker-сервисы.

## Миграции

Alembic файлы лежат в `backend/migrations`.

Локально или на сервере миграции можно запустить так:

```bash
docker-compose run --rm backend alembic upgrade head
```

Первая миграция является baseline текущей схемы и написана идемпотентно, чтобы
безопасно пройти на уже существующей production БД.

## Тесты

Backend unit tests запускаются так:

```bash
docker-compose run --rm backend pytest
```

## Просмотр

Production URL: `https://ai-seo-content-panel.site`.
