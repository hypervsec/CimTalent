up:
	docker compose up --build
down:
	docker compose down
build:
	docker compose build
logs:
	docker compose logs -f
backend-logs:
	docker compose logs -f backend
frontend-logs:
	docker compose logs -f frontend
migrate:
	docker compose exec backend alembic upgrade head
test:
	docker compose exec backend pytest -q
seed:
	docker compose exec backend python -m app.scripts.seed_demo
smoke:
	docker compose exec backend python -m app.scripts.demo_smoke
test-backend:
	docker compose exec backend pytest -q
test-frontend:
	docker compose exec frontend true
lint:
	docker compose exec backend ruff check app tests
clean:
	docker compose down -v
