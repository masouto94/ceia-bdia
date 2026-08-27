COMPOSE := docker compose -f compose.yaml

config:
	$(COMPOSE) config

layout:
	test -f backend/Dockerfile
	test -f backend/app/main.py
	test -f frontend/Dockerfile
	test -f frontend/index.html
	test -f landing/Dockerfile
	test -f landing/index.html
	test ! -e apps
	test ! -e services

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

reset-local:
	$(COMPOSE) down -v --remove-orphans

logs:
	$(COMPOSE) logs -f
