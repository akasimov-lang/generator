#!/bin/sh
set -eu

cd /home/akasimov/generator

docker compose \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  run --rm certbot renew --webroot -w /var/www/certbot --quiet

docker compose \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  exec -T nginx nginx -s reload
