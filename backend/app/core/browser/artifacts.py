from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from app.core.browser.exceptions import BrowserArtifactError
from app.core.browser.page_guard import sanitize_url

SAFE_NAME = re.compile(r"[^a-zA-Z0-9_.-]+")


class ArtifactPage(Protocol):
    @property
    def url(self) -> str: ...
    async def screenshot(self, *, path: str, full_page: bool) -> None: ...
    async def content(self) -> str: ...


class BrowserArtifactManager:
    def __init__(self, directory: Path, *, save_screenshot: bool, save_html: bool) -> None:
        self.directory = directory.resolve(strict=False)
        self.save_screenshot = save_screenshot
        self.save_html = save_html

    async def capture(
        self,
        page: ArtifactPage,
        *,
        event: str,
        correlation_id: str | None,
        exception: Exception,
    ) -> list[Path]:
        timestamp = datetime.now(UTC)
        stem = "_".join(
            (
                timestamp.strftime("%Y%m%dT%H%M%S%fZ"),
                self._sanitize(event),
                self._sanitize(correlation_id or "none"),
            )
        )
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            created: list[Path] = []
            if self.save_screenshot:
                screenshot = self._target(f"{stem}.png")
                await page.screenshot(path=str(screenshot), full_page=True)
                created.append(screenshot)
            if self.save_html:
                html = self._target(f"{stem}.html")
                html.write_text(await page.content(), encoding="utf-8")
                created.append(html)
            metadata = self._target(f"{stem}.json")
            metadata.write_text(
                json.dumps(
                    {
                        "event": event,
                        "sanitized_url": sanitize_url(page.url),
                        "timestamp": timestamp.isoformat(),
                        "exception_type": type(exception).__name__,
                        "correlation_id": correlation_id,
                    }
                ),
                encoding="utf-8",
            )
            created.append(metadata)
            return created
        except (OSError, ValueError) as exc:
            raise BrowserArtifactError("Browser artifact could not be created.") from exc

    def cleanup(self, retention_days: int, *, now: datetime | None = None) -> int:
        if not self.directory.exists():
            return 0
        threshold = (now or datetime.now(UTC)) - timedelta(days=retention_days)
        removed = 0
        for path in self.directory.iterdir():
            if path.is_file() and not path.is_symlink():
                modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
                if modified < threshold:
                    path.unlink()
                    removed += 1
        return removed

    def _target(self, name: str) -> Path:
        target = (self.directory / name).resolve(strict=False)
        if target.parent != self.directory:
            raise BrowserArtifactError("Artifact path traversal is not allowed.")
        return target

    @staticmethod
    def _sanitize(value: str) -> str:
        return SAFE_NAME.sub("-", value).strip("-._")[:80] or "unknown"
