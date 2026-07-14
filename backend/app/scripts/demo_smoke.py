# mypy: disable-error-code="no-untyped-def,no-untyped-call"
import json
import os
import sys
from urllib.error import URLError
from urllib.request import urlopen

BASE = os.getenv("DEMO_SMOKE_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")


def get(path):
    try:
        with urlopen(BASE + path, timeout=10) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"{path}: HTTP {response.status}")
            return json.load(response)
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"{path}: unavailable") from exc


def main():
    get("/health")
    jobs = get("/jobs?page=1&page_size=10")
    candidates = get("/candidates?page=1&page_size=20")
    if len(jobs.get("items", [])) < 3 or len(candidates.get("items", [])) < 10:
        raise RuntimeError("Demo seed counts are insufficient")
    job = jobs["items"][0]["id"]
    for path in (
        f"/jobs/{job}",
        f"/jobs/{job}/requirements",
        f"/jobs/{job}/queries",
        f"/jobs/{job}/search-results",
        f"/jobs/{job}/matches",
        f"/jobs/{job}/shortlist",
    ):
        get(path)
    print("demo smoke: ok")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"demo smoke: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
