# TalentFilter AI

TalentFilter AI, iş ilanı ayrıştırma, aday keşfi, enrichment, eşleştirme ve recruiter shortlist süreçleri için uçtan uca MVP’dir.

## Mimari

`frontend` React/Vite uygulamasıdır; Nginx `/api/` çağrılarını FastAPI `backend` servisine yönlendirir. Backend Alembic migration’larıyla PostgreSQL `db` servisini kullanır. Compose servisleri: `db`, `backend`, `frontend`.

## Hızlı başlangıç

Windows:

`copy .env.example .env`

`docker compose up --build`

Linux/macOS:

`cp .env.example .env`

`docker compose up --build`

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Migration, demo seed ve smoke

`docker compose exec backend alembic upgrade head`

`docker compose exec backend python -m app.scripts.seed_demo`

`docker compose exec backend python -m app.scripts.demo_smoke`

## Test ve manuel geliştirme

Backend: `cd backend` ardından `pytest`, `ruff check app tests`, `mypy app`.

Frontend: `cd frontend`, `npm install`, ardından `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`.

Makefile: `up`, `down`, `build`, `logs`, `backend-logs`, `frontend-logs`, `migrate`, `seed`, `smoke`, `test-backend`, `test-frontend`, `test`, `lint`, `clean`.

## Uçtan uca demo

Demo ilanını açın, requirement ve X-Ray sorgularını inceleyin; SearchResult’tan aday keşfedin, fixture enrichment çalıştırın, match detayını görüntüleyin, shortlist not/durumunu güncelleyin ve CSV indirin.

## LinkedIn ve güvenlik

Fixture enrichment varsayılan olarak açıktır ve ağ çağrısı gerektirmez. Live LinkedIn özelliği varsayılan kapalıdır. `.env`, `.sessions` ve `.artifacts` kaynak kontrolüne alınmamalıdır; production için örnek şifreler değiştirilmeli ve güçlü secret’lar kullanılmalıdır.

## Bilinen sınırlamalar

Bu MVP’de auth, Redis/Celery/worker, LLM/embedding, canlı kişi araması, production TLS ve cloud deployment yoktur.
