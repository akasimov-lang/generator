# Deploy

Production deploy идет через git push на сервер.

## Remote

```bash
git remote add production ssh://root@91.199.133.86/opt/generator/repo.git
```

В этом проекте SSH удобнее запускать через local config:

```bash
ssh -F .ssh/config generator-server
```

## Deploy

```bash
git push production main
```

На сервере настроен bare repository:

- repo: `/opt/generator/repo.git`
- worktree: `/opt/generator/app`
- deploy hook: `/opt/generator/repo.git/hooks/post-receive`

Hook после push:

1. Checkout `main` в `/opt/generator/app`.
2. Проверяет наличие `.env`.
3. Запускает `docker-compose up -d --build`.

## Просмотр

Пока домена нет:

```text
http://91.199.133.86
```

