# play_fetcher.py
import asyncio
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext

LAST_SEEN_FILE = Path("last_seen.json")
CACHE_TTL = 300  # segundos por defecto

def _load_last_seen() -> Dict[str, Any]:
    if not LAST_SEEN_FILE.exists():
        return {}
    try:
        return json.loads(LAST_SEEN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_last_seen(d: Dict[str, Any]) -> None:
    try:
        LAST_SEEN_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

class CatharsisFetcher:
    def __init__(self, headless: bool = True, max_concurrency: int = 1, cache_ttl: int = CACHE_TTL):
        self.headless = headless
        self.max_concurrency = max_concurrency
        self.cache_ttl = cache_ttl
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._sema = asyncio.Semaphore(max_concurrency)
        self._cache: Dict[str, tuple] = {}  # slug -> (ts, data)
        self._last_seen = _load_last_seen()

    async def start(self):
        if self._playwright:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
            ],
        )
        self._context = await self._browser.new_context()

    async def stop(self):
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def _fetch_xhr_json(self, slug: str, timeout: int = 20000) -> Optional[Dict[str, Any]]:
        api_url = f"https://newcatharsis.dig-it.info/api/mangas/{slug}"
        page = await self._context.new_page()
        result = {"data": None}

        async def on_response(resp):
            try:
                if resp.url.startswith(api_url) and resp.status == 200:
                    data = await resp.json()
                    result["data"] = data
            except Exception:
                pass

        page.on("response", on_response)
        page_url = f"https://newcatharsis.dig-it.info/manga/{slug}"
        try:
            await page.goto(page_url, wait_until="networkidle", timeout=timeout)
            await asyncio.sleep(0.25)
            if result["data"]:
                return result["data"]

            maybe = await page.evaluate("() => window.__INITIAL_STATE__ || window.__PRELOADED_STATE__ || null")
            if maybe:
                return maybe

            try:
                js = f"() => fetch('{api_url}', {{ credentials: 'include' }}).then(r => r.ok ? r.json() : null).catch(() => null)"
                fallback = await page.evaluate(js)
                return fallback
            except Exception:
                return None
        finally:
            try:
                await page.close()
            except Exception:
                pass

    async def fetch_manga(self, slug: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        entry = self._cache.get(slug)
        if entry and (now - entry[0]) < self.cache_ttl:
            return entry[1]

        await self.start()
        async with self._sema:
            try:
                data = await self._fetch_xhr_json(slug)
                if data:
                    self._cache[slug] = (time.time(), data)
                return data
            except Exception:
                return None

    def _parse_latest(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        caps = data.get("capitulos") or []
        if not caps:
            return None
        def ts_key(c):
            return c.get("fecha_publicacion") or c.get("date_created") or ""
        caps_sorted = sorted(caps, key=lambda c: ts_key(c) or "", reverse=True)
        return caps_sorted[0]

    async def check_and_notify(self, slug: str) -> (bool, Optional[Dict[str, Any]]):
        data = await self.fetch_manga(slug)
        if not data:
            return False, None
        latest = self._parse_latest(data)
        if not latest:
            return False, data
        latest_id = latest.get("id")
        last = self._last_seen.get(slug)
        if last != latest_id:
            self._last_seen[slug] = latest_id
            _save_last_seen(self._last_seen)
            return True, {"api": data, "latest": latest}
        return False, {"api": data, "latest": latest}
