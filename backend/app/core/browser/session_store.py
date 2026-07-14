from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from app.core.browser.exceptions import InvalidSessionStateError, SessionFileMissingError

MAX_STORAGE_STATE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class SessionFileMetadata:
    exists: bool
    valid: bool
    size_bytes: int | None = None
    modified_at: datetime | None = None
    has_linkedin_cookie: bool = False


class LinkedInSessionStore:
    def __init__(self, path: Path, *, max_bytes: int = MAX_STORAGE_STATE_BYTES) -> None:
        self.path = self._validate_path(path)
        self.max_bytes = max_bytes

    def exists(self) -> bool:
        return self.path.is_file() and not self.path.is_symlink()

    def load_storage_state(self) -> dict[str, object]:
        if not self.exists():
            raise SessionFileMissingError("LinkedIn session file is missing.")
        if self.path.stat().st_size > self.max_bytes:
            raise InvalidSessionStateError("LinkedIn session file exceeds the size limit.")
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise InvalidSessionStateError("LinkedIn session file is not valid JSON.") from exc
        return self._validate_state(raw)

    def validate_storage_state_file(self) -> bool:
        self.load_storage_state()
        return True

    def save_storage_state(self, state: Mapping[str, object]) -> None:
        validated = self._validate_state(dict(state))
        encoded = json.dumps(validated, ensure_ascii=False, separators=(",", ":")).encode()
        if len(encoded) > self.max_bytes:
            raise InvalidSessionStateError("LinkedIn session state exceeds the size limit.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".linkedin-", dir=self.path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                temporary.chmod(0o600)
            except OSError:
                pass
            os.replace(temporary, self.path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise InvalidSessionStateError("LinkedIn session state could not be saved.") from exc

    def delete_storage_state(self) -> None:
        if self.path.is_symlink():
            raise InvalidSessionStateError("Symlink session files are not allowed.")
        self.path.unlink(missing_ok=True)

    def metadata(self) -> SessionFileMetadata:
        if not self.exists():
            return SessionFileMetadata(False, False)
        stat = self.path.stat()
        try:
            state = self.load_storage_state()
        except InvalidSessionStateError:
            return SessionFileMetadata(
                True, False, stat.st_size, datetime.fromtimestamp(stat.st_mtime, UTC)
            )
        cookies = cast(list[object], state["cookies"])
        has_linkedin = any(
            isinstance(cookie, dict)
            and isinstance(cookie.get("domain"), str)
            and str(cookie["domain"]).casefold().endswith("linkedin.com")
            for cookie in cookies
        )
        return SessionFileMetadata(
            True,
            True,
            stat.st_size,
            datetime.fromtimestamp(stat.st_mtime, UTC),
            has_linkedin,
        )

    @staticmethod
    def _validate_path(path: Path) -> Path:
        if ".." in path.parts:
            raise InvalidSessionStateError("Session path traversal is not allowed.")
        resolved_parent = path.parent.resolve(strict=False)
        target = resolved_parent / path.name
        if target.exists() and target.is_symlink():
            raise InvalidSessionStateError("Symlink session files are not allowed.")
        return target

    @staticmethod
    def _validate_state(raw: object) -> dict[str, object]:
        if not isinstance(raw, dict):
            raise InvalidSessionStateError("Storage state must be a JSON object.")
        cookies = raw.get("cookies")
        origins = raw.get("origins", [])
        if not isinstance(cookies, list):
            raise InvalidSessionStateError("Storage state cookies must be a list.")
        if not isinstance(origins, list):
            raise InvalidSessionStateError("Storage state origins must be a list.")
        return {"cookies": cookies, "origins": origins}
