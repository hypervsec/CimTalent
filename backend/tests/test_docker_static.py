from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_docker_static_contract() -> None:
    compose = (ROOT / "docker-compose.yml").read_text()
    entrypoint = (ROOT / "backend/docker-entrypoint.sh").read_bytes()
    nginx = (ROOT / "frontend/nginx.conf").read_text()
    env = (ROOT / ".env.example").read_text()
    assert all(f"  {name}:" in compose for name in ("db", "backend", "frontend"))
    assert compose.count("healthcheck:") >= 3 and "postgres_data" in compose
    assert b"\r\n" not in entrypoint and b"seed_demo" in entrypoint
    assert "backend:8000" in nginx and "try_files" in nginx
    assert "POSTGRES_DB" in env and "DATABASE_URL" in env
    assert (ROOT / "backend/Dockerfile").is_file() and (ROOT / "frontend/Dockerfile").is_file()
    assert (ROOT / "backend/.dockerignore").is_file() and (
        ROOT / "frontend/.dockerignore"
    ).is_file()
