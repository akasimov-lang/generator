.PHONY: up down logs ps deploy

up:
	docker-compose up -d --build

down:
	docker-compose down

logs:
	docker-compose logs -f --tail=120

ps:
	docker-compose ps

deploy:
	git push production main
