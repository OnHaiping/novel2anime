.PHONY: up down logs test lint doctor

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

test:
	docker compose run --rm backend pytest -q

lint:
	docker compose run --rm backend ruff check app tests

doctor:
	curl -fsS http://localhost:3301/api/system/diagnostics | python -m json.tool

