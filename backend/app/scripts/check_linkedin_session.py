from __future__ import annotations

import asyncio

from app.config import get_settings
from app.core.browser.session_inspector import LinkedInSessionInspector, SessionHealthStatus


async def check_session() -> int:
    result = await LinkedInSessionInspector(get_settings()).inspect()
    print(f"LinkedIn session status: {result.status.value}. {result.message}")
    if result.status is SessionHealthStatus.AUTHENTICATED:
        return 0
    if result.status is SessionHealthStatus.CHALLENGE:
        return 2
    return 1


def main() -> None:
    raise SystemExit(asyncio.run(check_session()))


if __name__ == "__main__":
    main()
