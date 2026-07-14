#!/bin/sh
set -eu
python - <<'PY'
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
async def main():
  engine=create_async_engine(os.environ["DATABASE_URL"])
  for _ in range(30):
    try:
      async with engine.connect(): return
    except Exception: await asyncio.sleep(2)
  raise SystemExit("Database did not become available")
asyncio.run(main())
PY
alembic upgrade head
if [ "${SEED_DEMO_DATA:-true}" = "true" ]; then
  python -m app.scripts.seed_demo
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
