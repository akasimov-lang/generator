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
# Runtime VPN access rules stay on this server and are never taken from Git.
vpn_source=${PAGEPILOT_VPN_WHITELIST:-/home/akasimov/pagepilot-server/whitelist_vpn.conf}
[ -s "$vpn_source" ] || { echo 'Missing server VPN whitelist; deployment stopped before checkout.' >&2; exit 1; }
vpn_target="$worktree/infra/nginx/whitelists/whitelist_vpn.conf"
restore_vpn() {
  # Existing runtime files may be root-owned. Do not rewrite identical rules.
  if ! cmp -s "$vpn_source" "$vpn_target"; then
    mkdir -p "$(dirname "$vpn_target")"
    cp -p "$vpn_source" "$vpn_target"
  fi
  cmp -s "$vpn_source" "$vpn_target"
}
trap restore_vpn EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
git --git-dir="$repo" --work-tree="$worktree" checkout -f main
restore_vpn
trap - EXIT HUP INT TERM
cd "$worktree"
test -f .env
compose() { docker compose -f docker-compose.yml -f docker-compose.production.yml "$@"; }
compose build
# Validate broker transport compatibility before replacing running services.
compose run --rm --no-deps backend python -c "from kombu.transport.redis import Channel; Channel.__new__(Channel)._get_client()"
compose up -d postgres redis
compose run --rm backend alembic upgrade head
compose up -d --remove-orphans
compose exec -T nginx nginx -t
compose exec -T nginx nginx -s reload
attempt=1
while [ "$attempt" -le 30 ]; do
  if compose exec -T backend curl -fsS http://127.0.0.1:8000/api/health >/dev/null \
    && compose exec -T nginx wget -q -O /dev/null http://backend:8000/api/health \
    && compose exec -T nginx wget -q -O /dev/null http://frontend:80/ \
    && compose ps --status running --services | grep -qx celery_beat \
    && compose exec -T backend python -c "from app.worker import celery_app; replies=celery_app.control.inspect(timeout=2).ping() or {}; expected={'generation','menu','publication','automation','short_generation','planning','background_dispatch','confirmation','cache_sync','maintenance'}; missing=expected-{name.split('@')[0] for name in replies}; print('Workers missing:', sorted(missing)) if missing else None; raise SystemExit(bool(missing))"; then
    printf '%s\n' "$revision" > "$repo/deployed-revision"
    echo "Production health checks passed: $revision"
    exit 0
  fi
  attempt=$((attempt + 1))
  sleep 2
done
echo "Production health checks failed for $revision; inspect services and restore the last healthy release if needed." >&2
exit 1
