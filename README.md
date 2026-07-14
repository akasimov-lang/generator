# Content Generator Admin

Самописная админка для управления AI-генерацией SEO-контента и публикацией
готовых JSON-данных в существующую систему через endpoint.

## Что внутри

- `frontend` - React/Vite админка без Tailwind и без CDN.
- `backend` - FastAPI API, валидация, задачи генерации и публикации.
- `infra/nginx` - production reverse proxy под доступ по IP.
- `docker-compose.yml` - полный запуск: frontend, backend, postgres, redis,
  celery worker, celery beat, nginx.

## Локальный/серверный запуск

```bash
cp .env.example .env
docker-compose up -d --build
```

После запуска:

- UI: `http://91.199.133.86`
- API health: `http://91.199.133.86/api/health`

## Доступ

Логин и пароль задаются в `.env`:

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me
```

## Git deploy

Проект рассчитан на push-деплой по SSH-ключу на сервер.
Рабочее подключение:

```bash
ssh -F .ssh/config generator-server
```

После настройки production remote:

```bash
git push production main
```

## Миграции и проверки

Схема БД ведется через Alembic. Применить миграции:

```bash
make migrate
```

Базовые backend-тесты:

```bash
make test
```

На production deploy hook запускает `alembic upgrade head` перед перезапуском
сервисов.
