# Production deploy

Единственный штатный способ изменения кода production — Git.
Не копируйте исходники через scp/rsync/docker cp и не редактируйте их на сервере.
Секреты `.env`, сертификаты, БД и резервные копии хранятся отдельно от исходников.
VPN whitelist, Docker/Nginx и скрипты деплоя являются кодом и версионируются.

## Порядок

1. Подготовьте коммит на актуальной `main`. Сохраните независимые локальные задачи;
   при грязном дереве используйте отдельный checkout/worktree, не `git add -A` в нём.
2. Выполните проверки по задаче: `python scripts/check_changes.py <файлы>` и `--run`.
   Для неизвестного узла задайте связанный тест через `--test`.
   Браузерные проверки на Mac не запускаются. Полный backend-набор — при изменении
   общих моделей, БД или инфраструктуры тестов, согласно AGENTS.md.
3. `git push origin main`, затем `git push production main`.
4. Дождитесь строки `Production health checks passed: <SHA>` и убедитесь,
   что SHA совпадает с `main` и файлом `generator.git/deployed-revision`.
   Успешный git push сам по себе не подтверждает успех post-receive/deploy.

Ручной GitHub Actions workflow `Deploy` также выполняет git push в production bare repo
и сверяет deployed-revision. Старый rsync workflow удалён. `DEPLOY_PATH` задаёт
путь рабочего каталога, путь bare repo вычисляется добавлением `.git`.

Production: https://ai-seo-content-panel.site
SSH: `ssh -F .ssh/config seotech-web-autocontent`
Git: `/home/akasimov/generator.git`; рабочие файлы: `/home/akasimov/generator`.

## Версионируемые hooks

`pre-receive` блокирует non-fast-forward и выкладку поверх правок/новых исходников
на сервере. При отказе сначала сохраните и согласуйте эти изменения в Git;
не обходите проверку и не стирайте рабочие файлы.
`post-receive` запускает `scripts/deploy-production.sh` из принятого коммита.
Скрипт блокирует параллельную выкладку, собирает образы, применяет миграции,
обновляет сервисы, перезагружает Nginx и проверяет backend и frontend.

Однократная установка hooks, а также обновление после их изменения:

```sh
repo=/home/akasimov/generator.git
for hook in pre-receive post-receive; do
  git --git-dir="$repo" show "main:scripts/git-hooks/$hook" > "$repo/hooks/$hook.new"
  chmod +x "$repo/hooks/$hook.new"
  mv "$repo/hooks/$hook.new" "$repo/hooks/$hook"
done
```

При аварии восстанавливайте известный здоровый коммит через revert и обычный
push; отдельно учитывайте совместимость миграций. Перед первой синхронизацией
сохранён снимок исходников и прежних hooks вне рабочего дерева.

История восстановления Git: [аудит 2 ноября 2026](production-git-audit-2026-11-02.md).

## Восстановление старого журнала Alembic

Для снимка 2 ноября 2026 миграции 0065–0069 были фактически применены,
но не записаны в alembic_version. Одноразовый скрипт
`backend/scripts/reconcile_production_migrations.py` без флагов выполняет
только сверку схемы; `--apply` после успешной сверки выравнивает только журнал.
Это не замена `alembic upgrade head` для новых миграций и не безусловный stamp.
