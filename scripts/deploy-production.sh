#!/bin/sh
set -eu
repo=${PAGEPILOT_REPOSITORY:-/home/akasimov/generator.git}
worktree=${PAGEPILOT_WORK_TREE:-/home/akasimov/generator}
revision=${1:?Expected main commit SHA}
exec 9>"$repo/deploy.lock"
flock -n 9 || { echo 'Another deployment is running.' >&2; exit 1; }
[ "$(git --git-dir="$repo" rev-parse refs/heads/main)" = "$revision" ] || {
  echo 'Main moved after this push; refusing to deploy an outdated commit.' >&2; exit 1;
}
git --git-dir="$repo" --work-tree="$worktree" checkout -f main
cd "$worktree"
test -f .env
compose() { docker compose -f docker-compose.yml -f docker-compose.production.yml "$@"; }
compose build
compose up -d postgres redis
compose run --rm backend alembic upgrade head
compose up -d
compose exec -T nginx nginx -t
compose exec -T nginx nginx -s reload
attempt=1
while [ "$attempt" -le 30 ]; do
  if compose exec -T backend curl -fsS http://127.0.0.1:8000/api/health >/dev/null \
    && compose exec -T nginx wget -q -O /dev/null http://backend:8000/api/health \
    && compose exec -T nginx wget -q -O /dev/null http://frontend:80/; then
    printf '%s\n' "$revision" > "$repo/deployed-revision"
    echo "Production health checks passed: $revision"
    exit 0
  fi
  attempt=$((attempt + 1))
  sleep 2
done
echo "Production health checks failed for $revision; inspect services and restore the last healthy release if needed." >&2
exit 1
