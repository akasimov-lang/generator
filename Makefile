.PHONY: up down logs ps migrate test deploy

up:
	docker-compose up -d --build

down:
	docker-compose down

logs:
	docker-compose logs -f --tail=120

ps:
	docker-compose ps

migrate:
	docker-compose run --rm backend alembic upgrade head

test:
	docker-compose run --rm backend pytest

deploy:
	git push production main
