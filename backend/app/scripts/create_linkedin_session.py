from __future__ import annotations

import asyncio
from time import monotonic

from app.config import get_settings
from app.core.browser.exceptions import (
    AuthenticationRequiredError,
    CaptchaDetectedError,
    ChallengeDetectedError,
)
from app.core.browser.manager import BrowserManager
from app.core.browser.session_store import LinkedInSessionStore


async def create_session() -> int:
    base = get_settings()
    settings = base.model_copy(update={"browser_headless": False})
    store = LinkedInSessionStore(settings.linkedin_session_file)
    print("Chromium açılıyor. Giriş bilgilerinizi yalnız LinkedIn sayfasına manuel girin.")
    async with BrowserManager(settings, session_store=store) as browser:
        page = await browser.new_page()
        await page.goto(f"{settings.linkedin_base_url.rstrip('/')}/login")
        deadline = monotonic() + settings.linkedin_login_timeout_seconds
        while monotonic() < deadline:
            await asyncio.sleep(1)
            try:
                await browser.page_guard.inspect(page)
            except AuthenticationRequiredError:
                continue
            except (ChallengeDetectedError, CaptchaDetectedError):
                print("Manuel güvenlik doğrulaması bekleniyor; script engeli aşmaya çalışmayacak.")
                continue
            if "/login" not in page.url and "/checkpoint" not in page.url:
                store.save_storage_state(await browser.storage_state())
                print(f"LinkedIn session güvenli biçimde kaydedildi: {store.path}")
                return 0
    print("LinkedIn giriş süresi doldu; session kaydedilmedi.")
    return 1


def main() -> None:
    raise SystemExit(asyncio.run(create_session()))


if __name__ == "__main__":
    main()
