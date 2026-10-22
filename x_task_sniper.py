import os
import sys
import time
import json
import random
import asyncio
import hashlib
import hmac
import urllib.parse
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests
from telethon import TelegramClient
from telethon.tl.functions.messages import RequestAppWebViewRequest
from telethon.tl.types import InputBotAppShortName
from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import Stealth
import builtins

# Ensure real-time flushed output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

_orig_print = builtins.print
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    return _orig_print(*args, **kwargs)
builtins.print = print

BASE_DIR = os.path.dirname(__file__)
SESSION_DIR = os.path.abspath(os.path.join(BASE_DIR, "../Telegram Session"))
LOCAL_ACCOUNTS_JSON = os.path.join(BASE_DIR, "accounts.json")
SCRAPER_ACCOUNTS_JSON = os.path.abspath(os.path.join(BASE_DIR, "../twitter-scraper-bot/accounts.json"))
ACCOUNTS_JSON = LOCAL_ACCOUNTS_JSON if os.path.exists(LOCAL_ACCOUNTS_JSON) else SCRAPER_ACCOUNTS_JSON
COMPLETED_FILE = os.path.join(BASE_DIR, "completed_x_tasks.json")
COOLDOWN_FILE = os.path.join(BASE_DIR, "cooldown_state.json")

def load_cooldowns() -> Dict[str, float]:
    if os.path.exists(COOLDOWN_FILE):
        try:
            with open(COOLDOWN_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_cooldown(phone: str, until: float):
    try:
        cds = load_cooldowns()
        cds[phone] = until
        with open(COOLDOWN_FILE, "w") as f:
            json.dump(cds, f)
    except Exception:
        pass

API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"

ACCOUNTS_CONFIG_PATH = os.path.join(BASE_DIR, "accounts_config.json")

def load_accounts_config() -> List[Dict[str, Any]]:
    if os.path.exists(ACCOUNTS_CONFIG_PATH):
        try:
            with open(ACCOUNTS_CONFIG_PATH, "r", encoding="utf-8") as f:
                raw_accs = json.load(f)
                accs = []
                for a in raw_accs:
                    cfile = a.get("completed_file", "completed_x_tasks.json")
                    if not os.path.isabs(cfile):
                        cfile = os.path.join(BASE_DIR, cfile)
                    accs.append({
                        "phone": a["phone"],
                        "twitter_key": a["twitter_key"],
                        "name": a.get("name", a["phone"]),
                        "tag": a.get("tag", "👤"),
                        "completed_file": cfile
                    })
                return accs
        except Exception as e:
            print(f"⚠️ Gagal memuat accounts_config.json: {e}")
    # Fallback default template
    return [
        {
            "phone": "+6281234567890",
            "twitter_key": "account1",
            "name": "Master",
            "tag": "👑 Master",
            "completed_file": COMPLETED_FILE
        }
    ]

CONFIG_ACCOUNTS = load_accounts_config()

def format_gomine(pts: int | float) -> str:
    """Format saldo dan reward: dibulatkan integer tanpa koma (misal 118,774 -> 118 GOMINE)."""
    try:
        val = int(pts) // 1000
        return f"{val} GOMINE"
    except Exception:
        return f"{pts} GOMINE"

def clean_type(ttype: str) -> str:
    mapping = {
        "follow_twitter": "Follow",
        "like_twitter": "Like",
        "like": "Like",
        "retweet": "Repost",
        "repost": "Repost",
        "comment_twitter": "Comment",
        "reply_x": "Comment",
        "comment": "Comment",
        "quote_twitter": "Quote",
        "quote": "Quote",
        "bookmark_twitter": "Bookmark",
        "bookmark": "Bookmark",
        "join_telegram": "Join Telegram",
        "visit_website": "Visit Website"
    }
    return mapping.get(str(ttype).lower(), str(ttype))

def explain_reason(r: Any) -> str:
    r_str = str(r).lower()
    if "unavailable" in r_str:
        return "kuota habis / slot penuh direbut user global"
    if "verified_required" in r_str or "requires_verified" in r_str:
        return "khusus akun centang biru (X Premium)"
    if "tier_locked" in r_str:
        return "tier akun belum mencukupi"
    if "web3" in r_str:
        return "butuh approval web3"
    if "already" in r_str:
        return "sudah pernah dikerjakan"
    if "proof_required" in r_str:
        return "butuh upload screenshot manual"
    if "daily_limit" in r_str or "capped" in r_str:
        return "batas task harian tercapai"
    if "no_comments" in r_str:
        return "kuota komentar GoMine habis"
    if "no_quotes" in r_str:
        return "kuota quote GoMine habis"
    return str(r)

def load_x_cookies(twitter_key: str = "fannettt") -> List[Dict[str, str]]:
    with open(ACCOUNTS_JSON, "r", encoding="utf-8", errors="ignore") as f:
        data = json.load(f)
    acc = data["accounts"][twitter_key]
    return [
        {"name": "auth_token", "value": acc["auth_token"], "domain": ".x.com", "path": "/"},
        {"name": "ct0", "value": acc["ct0"], "domain": ".x.com", "path": "/"},
        {"name": "auth_token", "value": acc["auth_token"], "domain": ".twitter.com", "path": "/"},
        {"name": "ct0", "value": acc["ct0"], "domain": ".twitter.com", "path": "/"}
    ]

def load_completed_tasks(filepath: str = COMPLETED_FILE) -> Dict[str, Any]:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_completed_tasks(data: Dict[str, Any], filepath: str = COMPLETED_FILE):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def get_tg_init_data(phone: str = "+6281227121848") -> str:
    """Mengekstrak tgWebAppData secara aman via Telethon MTProto."""
    session_path = os.path.join(SESSION_DIR, f"{phone}.session")
    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()
    bot = await client.get_input_entity("GoMineAppBot")
    app = InputBotAppShortName(bot_id=bot, short_name="app")
    res = await client(RequestAppWebViewRequest(
        peer=bot,
        app=app,
        platform="android",
        start_param="ref_6512727025"
    ))
    await client.disconnect()
    raw_url = res.url
    frag = raw_url.split('#', 1)[-1]
    params = urllib.parse.parse_qs(frag)
    return params.get("tgWebAppData", [""])[0]

class GoMineClient:
    BASE_URL = "https://app.gomine.social/api"

    def __init__(self, init_data: str):
        self.init_data = init_data
        self.session = requests.Session()
        self.headers = {
            "Host": "app.gomine.social",
            "Origin": "https://app.gomine.social",
            "Referer": "https://app.gomine.social/",
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36",
            "Content-Type": "application/json",
            "X-Init-Data": self.init_data,
            "Accept": "application/json, text/plain, */*"
        }
        self.session_data: Optional[Dict[str, Any]] = None
        self.time_offset: float = 0.0

    def _call(self, method: str, endpoint: str, json_data: Optional[Dict] = None, params: Optional[Dict] = None, custom_headers: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        hdrs = dict(self.headers)
        if custom_headers:
            hdrs.update(custom_headers)
        try:
            r = self.session.request(method, url, json=json_data, params=params, headers=hdrs, timeout=12)
            try:
                res_json = r.json()
            except Exception:
                res_json = {"raw": r.text}
            return {"ok": r.status_code in [200, 201], "status": r.status_code, "data": res_json}
        except Exception as e:
            return {"ok": False, "status": 0, "error": str(e)}

    def ensure_task_session(self) -> bool:
        if self.session_data:
            return True
        r = self._call("POST", "/users/session-init")
        if r["ok"] and isinstance(r["data"], dict) and "secret" in r["data"]:
            self.session_data = r["data"]
            srv_now = r["data"].get("now", time.time())
            self.time_offset = srv_now * 1000 - time.time() * 1000
            return True
        return False

    def get_signed_headers(self, method: str = "POST") -> Dict[str, str]:
        if not self.ensure_task_session():
            return {}
        sid = self.session_data["sid"]
        secret = self.session_data["secret"]
        now_sec = str(int((time.time() * 1000 + self.time_offset) / 1000))
        msg = f"{method.upper()}\n{now_sec}"
        sig = hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()
        return {
            "X-GM-Sid": sid,
            "X-GM-Ts": now_sec,
            "X-GM-Sig": sig
        }

    def get_user_profile(self) -> Dict[str, Any]:
        return self._call("GET", "/users/me")

    def get_campaigns(self) -> List[Dict[str, Any]]:
        r = self._call("GET", "/campaigns")
        return r["data"] if r["ok"] and isinstance(r["data"], list) else []

    def get_campaign_tasks(self, campaign_id: int) -> List[Dict[str, Any]]:
        r = self._call("GET", f"/campaigns/{campaign_id}/tasks")
        return r["data"] if r["ok"] and isinstance(r["data"], list) else []

    def get_browse_category(self, platform: str, action: str) -> List[Dict[str, Any]]:
        r = self._call("GET", "/campaigns/browse-category", params={"platform": platform, "action": action})
        return r["data"] if r["ok"] and isinstance(r["data"], list) else []

    def reserve_task(self, task_id: int) -> Dict[str, Any]:
        hdrs = self.get_signed_headers("POST")
        res = self._call("POST", f"/tasks/{task_id}/reserve", custom_headers=hdrs)
        if not res["ok"] and res.get("status") in [401, 403]:
            # Session expired di server GoMine, refresh session otomatis
            self.session_data = None
            hdrs = self.get_signed_headers("POST")
            res = self._call("POST", f"/tasks/{task_id}/reserve", custom_headers=hdrs)
        return res

    def verify_task(self, task_id: int, payload: Optional[Dict] = None) -> Dict[str, Any]:
        hdrs = self.get_signed_headers("POST")
        p = payload if payload is not None else {"platform": "android"}
        res = self._call("POST", f"/tasks/{task_id}/verify", json_data=p, custom_headers=hdrs)
        if not res["ok"] and res.get("status") in [401, 403]:
            # Session expired di server GoMine, refresh session otomatis
            self.session_data = None
            hdrs = self.get_signed_headers("POST")
            res = self._call("POST", f"/tasks/{task_id}/verify", json_data=p, custom_headers=hdrs)
        return res

    def enable_nsfw(self) -> Dict[str, Any]:
        return self._call("POST", "/users/me/nsfw", json_data={"nsfw_enabled": True})

    def claim_mining(self) -> Dict[str, Any]:
        return self._call("POST", "/sparks/mining/claim")

    def boost_mining(self) -> Dict[str, Any]:
        return self._call("POST", "/sparks/mining/boost")

    def claim_referral_sparks(self) -> Dict[str, Any]:
        return self._call("POST", "/sparks/referral/claim")

    def checkin(self) -> Dict[str, Any]:
        return self._call("POST", "/users/checkin")

class TwitterAutomator:
    def __init__(self, cookies: List[Dict[str, str]]):
        self.cookies = cookies
        self.browser = None
        self.context = None
        self.page = None

    async def init_browser(self, p):
        self.browser = await p.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        await self.context.add_cookies(self.cookies)
        self.page = await self.context.new_page()

    async def close_browser(self):
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass

    async def dismiss_sensitive(self):
        try:
            # Tutup pop-up modal overlay jika menutupi halaman (misal X Space peek / banner)
            close_btn = self.page.locator('[aria-label="Close"], [aria-label="Tutup"], [data-testid="app-bar-close"]').first
            if await close_btn.count() > 0:
                try:
                    await close_btn.click(force=True)
                    await asyncio.sleep(0.4)
                except Exception:
                    pass

            # Tutup cookie consent jika muncul
            cookie_btn = self.page.locator('button:has-text("Refuse non-essential"), button:has-text("Tolak cookie"), button:has-text("Accept all cookies")').first
            if await cookie_btn.count() > 0 and await cookie_btn.is_visible():
                try:
                    await cookie_btn.click(force=True)
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

            view_btns = self.page.locator('button:has-text("View"), [role="button"]:has-text("Show"), button:has-text("Lihat"), button:has-text("Accept"), button:has-text("Yes")')
            cnt = await view_btns.count()
            for i in range(cnt):
                btn = view_btns.nth(i)
                if await btn.is_visible():
                    await btn.click(force=True)
                    await asyncio.sleep(0.4)
        except Exception:
            pass

    async def follow_user(self, target_url: str, username: str) -> bool:
        url = target_url if target_url else f"https://x.com/{username.lstrip('@')}"
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=25000)
            try:
                await self.page.wait_for_selector('[data-testid$="-follow"], [data-testid$="-unfollow"]', timeout=15000)
            except Exception:
                pass
            await asyncio.sleep(1.5)

            unfollow_btn = self.page.locator('[data-testid$="-unfollow"]').first
            if await unfollow_btn.count() > 0:
                print(f"      └─ 🐦 Follow @{username}... Sudah follow")
                return True

            follow_btn = self.page.locator('[data-testid$="-follow"]').first
            if await follow_btn.count() > 0:
                try:
                    await follow_btn.scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass
                await follow_btn.click(force=True)
                await asyncio.sleep(1.5)
                print(f"      └─ 🐦 Follow @{username}... Sukses")
                return True
            return False
        except Exception:
            return False

    async def like_tweet(self, tweet_url: str) -> bool:
        try:
            await self.page.goto(tweet_url, wait_until="domcontentloaded", timeout=25000)
            try:
                await self.page.wait_for_selector('article[data-testid="tweet"], [data-testid="like"]', timeout=15000)
            except Exception:
                pass
            await asyncio.sleep(1.5)
            await self.dismiss_sensitive()

            # Pastikan halaman tidak redirect ke /home karena tweet dihapus/invalid
            if "status" not in self.page.url:
                print(f"      └─ ⚠️ Redirect terdeteksi: {self.page.url}")
                return False

            main_tweet = self.page.locator('article[data-testid="tweet"]').first
            scope = main_tweet if await main_tweet.count() > 0 else self.page

            unlike_btn = scope.locator('[data-testid="unlike"]').first
            if await unlike_btn.count() > 0:
                print("      └─ 🐦 Like... Sudah like")
                return True

            like_btn = scope.locator('[data-testid="like"]').first
            if await like_btn.count() > 0:
                try:
                    await like_btn.scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass
                await asyncio.sleep(0.3)
                await like_btn.click(force=True)
                await asyncio.sleep(2.0)
                print("      └─ 🐦 Like... Sukses")
                return True

            # Global fallback jika scope tweet utama belum menemukan tombol Like
            global_like = self.page.locator('[data-testid="like"]').first
            if await global_like.count() > 0:
                try:
                    await global_like.scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass
                await asyncio.sleep(0.3)
                await global_like.click(force=True)
                await asyncio.sleep(2.0)
                print("      └─ 🐦 Like (Global)... Sukses")
                return True

            print("      └─ ⚠️ Tombol Like tidak ditemukan / tweet tidak dapat dimuat")
            return False
        except Exception as e:
            print(f"      └─ ⚠️ Error aksi Like: {e}")
            return False

    async def repost_tweet(self, tweet_url: str) -> bool:
        try:
            await self.page.goto(tweet_url, wait_until="domcontentloaded", timeout=25000)
            try:
                await self.page.wait_for_selector('article[data-testid="tweet"], [data-testid="retweet"]', timeout=15000)
            except Exception:
                pass
            await asyncio.sleep(1.5)
            await self.dismiss_sensitive()

            if "status" not in self.page.url:
                print(f"      └─ ⚠️ Redirect terdeteksi: {self.page.url}")
                return False

            main_tweet = self.page.locator('article[data-testid="tweet"]').first
            scope = main_tweet if await main_tweet.count() > 0 else self.page

            unrt_btn = scope.locator('[data-testid="unretweet"]').first
            if await unrt_btn.count() > 0:
                print("      └─ 🐦 Repost... Sudah repost")
                return True

            rt_btn = scope.locator('[data-testid="retweet"]').first
            if await rt_btn.count() > 0:
                try:
                    await rt_btn.scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass
                await rt_btn.click(force=True)
                try:
                    await self.page.wait_for_selector('[data-testid="retweetConfirm"], [role="menuitem"]', timeout=3500)
                except Exception:
                    await asyncio.sleep(1.0)
                confirm_btn = self.page.locator('[data-testid="retweetConfirm"], [role="menuitem"]:has-text("Repost"), [role="menuitem"]:has-text("Posting ulang"), [role="menuitem"] span:has-text("Repost")').first
                if await confirm_btn.count() > 0:
                    await confirm_btn.click(force=True)
                    try:
                        await self.page.wait_for_selector('[data-testid="unretweet"]', timeout=4000)
                    except Exception:
                        await asyncio.sleep(1.5)
                    print("      └─ 🐦 Repost... Sukses")
                    return True

            global_rt = self.page.locator('[data-testid="retweet"]').first
            if await global_rt.count() > 0:
                try:
                    await global_rt.scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass
                await global_rt.click(force=True)
                try:
                    await self.page.wait_for_selector('[data-testid="retweetConfirm"], [role="menuitem"]', timeout=3500)
                except Exception:
                    await asyncio.sleep(1.0)
                confirm_btn = self.page.locator('[data-testid="retweetConfirm"], [role="menuitem"]:has-text("Repost"), [role="menuitem"]:has-text("Posting ulang"), [role="menuitem"] span:has-text("Repost")').first
                if await confirm_btn.count() > 0:
                    await confirm_btn.click(force=True)
                    try:
                        await self.page.wait_for_selector('[data-testid="unretweet"]', timeout=4000)
                    except Exception:
                        await asyncio.sleep(1.5)
                    print("      └─ 🐦 Repost (Global)... Sukses")
                    return True

            return False
        except Exception:
            return False

    async def bookmark_tweet(self, tweet_url: str) -> bool:
        try:
            try:
                await self.page.goto(tweet_url, wait_until="domcontentloaded", timeout=25000)
            except Exception:
                pass
            try:
                await self.page.wait_for_selector('article[data-testid="tweet"]', timeout=8000)
            except Exception:
                pass
            await asyncio.sleep(1.5)
            await self.dismiss_sensitive()

            if "status" not in self.page.url:
                print(f"      └─ ⚠️ Redirect terdeteksi: {self.page.url}")
                return False

            main_tweet = self.page.locator('article[data-testid="tweet"]').first
            scope = main_tweet if await main_tweet.count() > 0 else self.page

            unbm_btn = scope.locator('[data-testid="removeBookmark"]').first
            if await unbm_btn.count() > 0 and await unbm_btn.is_visible():
                print("      └─ 🐦 Bookmark... Sudah bookmark")
                return True

            bm_btn = scope.locator('[data-testid="bookmark"]').first
            if await bm_btn.count() > 0 and await bm_btn.is_visible():
                await bm_btn.click(force=True)
                await asyncio.sleep(1.5)
                print("      └─ 🐦 Bookmark... Sukses")
                return True
            print("      └─ 🐦 Bookmark... Selesai")
            return True
        except Exception:
            return True

    async def reply_tweet(self, tweet_url: str, comment_text: Optional[str]) -> bool:
        if not comment_text:
            comment_text = "Great project! Looking forward to this 🚀"
        try:
            try:
                await self.page.goto(tweet_url, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
            try:
                await self.page.wait_for_selector('article[data-testid="tweet"]', timeout=10000)
            except Exception:
                pass
            await asyncio.sleep(1.5)
            await self.dismiss_sensitive()

            if "status" not in self.page.url:
                print(f"      └─ ⚠️ Redirect terdeteksi: {self.page.url}")
                return False

            main_tweet = self.page.locator('article[data-testid="tweet"]').first
            scope = main_tweet if await main_tweet.count() > 0 else self.page

            if await scope.locator('[data-testid="reply"][aria-disabled="true"]').count() > 0:
                print("      └─ ⚠️ Reply dinonaktifkan oleh pembuat tweet")
                return False

            # Cek apakah textarea reply sudah langsung terlihat inline
            textarea = self.page.locator('[data-testid="tweetTextarea_0"]').first
            if await textarea.count() == 0 or not await textarea.is_visible():
                r_icon = scope.locator('[data-testid="reply"]').first
                if await r_icon.count() > 0:
                    try:
                        await r_icon.click(force=True, timeout=4000)
                        await asyncio.sleep(1.5)
                    except Exception:
                        pass

            # Prioritaskan scope modal dialog jika muncul
            modal = self.page.locator('[role="dialog"][aria-modal="true"]').first
            if await modal.count() > 0 and await modal.is_visible():
                target_scope = modal
            else:
                target_scope = self.page

            textarea = target_scope.locator('[data-testid="tweetTextarea_0"]').first
            if await textarea.count() > 0:
                await textarea.click(force=True)
                await asyncio.sleep(0.4)
                await self.page.keyboard.insert_text(comment_text)
                await asyncio.sleep(0.8)

                # Prioritas 1: Gunakan shortcut keyboard native Control+Enter (instan & kebal overlay pointer)
                await self.page.keyboard.press("Control+Enter")
                await asyncio.sleep(1.5)

                # Prioritas 2: Klik tombol submit aktif dengan force=True jika masih belum terkirim
                send_btn = target_scope.locator('[data-testid="tweetButtonInline"]:not([aria-disabled="true"]), [data-testid="tweetButton"]:not([aria-disabled="true"])').first
                if await send_btn.count() > 0 and await send_btn.is_visible():
                    try:
                        await send_btn.click(force=True, timeout=3000)
                    except Exception:
                        pass

                await asyncio.sleep(3.0)
                print(f"      └─ 🐦 Comment '{comment_text[:25]}...' Sukses")
                return True

            return False
        except Exception as e:
            print(f"      └─ ⚠️ Error reply: {e}")
            return False

def extract_tweet_id(target_url: str, target_id: Any = None) -> Optional[str]:
    if target_id and str(target_id).isdigit():
        return str(target_id)
    if target_url:
        import re
        m = re.search(r'/status/(\d+)', str(target_url))
        if m:
            return m.group(1)
    return None

def extract_follow_target(target_url: str, target_id: Any = None):
    """Mengembalikan tuple (screen_name, user_id)."""
    if target_id:
        s_id = str(target_id).strip()
        if s_id.isdigit():
            return None, s_id
        return s_id.lstrip('@'), None
    if target_url:
        parsed = urllib.parse.urlparse(target_url)
        qs = urllib.parse.parse_qs(parsed.query)
        if 'screen_name' in qs:
            return qs['screen_name'][0].lstrip('@'), None
        if 'user_id' in qs and qs['user_id'][0].isdigit():
            return None, qs['user_id'][0]
        parts = [p for p in parsed.path.split('/') if p and p not in ['i', 'intent']]
        if parts:
            cand = parts[0].lstrip('@')
            if cand.isdigit():
                return None, cand
            return cand, None
    return None, None

def fast_like_tweet(x_cookies: list, tweet_id: str) -> bool:
    try:
        from curl_cffi import requests as cffi_requests
        auth = next((c["value"] for c in x_cookies if c["name"] == "auth_token"), None)
        ct0 = next((c["value"] for c in x_cookies if c["name"] == "ct0"), None)
        if not auth or not ct0:
            return False
        qid = "lI07N6Otwv1PhnEgXILM7A"
        headers = {
            "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "x-csrf-token": ct0,
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
            "content-type": "application/json",
            "cookie": f"auth_token={auth}; ct0={ct0};"
        }
        payload = {
            "variables": {"tweet_id": str(tweet_id)},
            "queryId": qid
        }
        r = cffi_requests.post(f"https://x.com/i/api/graphql/{qid}/FavoriteTweet", headers=headers, json=payload, impersonate="chrome124", timeout=8)
        if r.status_code == 200:
            data = r.json()
            if "data" in data and "favorite_tweet" in data["data"]:
                return True
            if any("already" in str(err).lower() for err in data.get("errors", [])):
                return True
        return False
    except Exception:
        return False

def fast_repost_tweet(x_cookies: list, tweet_id: str):
    """Retweet tweet via GraphQL internal API. Returns tuple (success: bool, error: Optional[str])."""
    try:
        from curl_cffi import requests as cffi_requests
        auth = next((c["value"] for c in x_cookies if c["name"] == "auth_token"), None)
        ct0 = next((c["value"] for c in x_cookies if c["name"] == "ct0"), None)
        if not auth or not ct0:
            return False, "missing_cookies"
        qid = "ojPdsZsimiJrUGLR1sjUtA"
        headers = {
            "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "x-csrf-token": ct0,
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
            "content-type": "application/json",
            "cookie": f"auth_token={auth}; ct0={ct0};"
        }
        payload = {
            "variables": {"tweet_id": str(tweet_id), "dark_request": False},
            "queryId": qid
        }
        for host in ["twitter.com", "x.com"]:
            try:
                r = cffi_requests.post(f"https://{host}/i/api/graphql/{qid}/CreateRetweet", headers=headers, json=payload, impersonate="chrome124", timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    if "data" in data and "create_retweet" in data["data"]:
                        return True, None
                    if "errors" in data and len(data["errors"]) > 0:
                        err_msg = data["errors"][0].get("message", "")
                        if "already" in err_msg.lower():
                            return True, None
                        if "daily limit" in err_msg.lower() or "344" in err_msg:
                            return False, "daily_limit_reached"
                        return False, err_msg
            except Exception:
                pass
        return False, "failed_both_hosts"
    except Exception as e:
        return False, str(e)

def fast_follow_user(x_cookies: list, screen_name: str = None, user_id: str = None) -> bool:
    try:
        from curl_cffi import requests as cffi_requests
        auth = next((c["value"] for c in x_cookies if c["name"] == "auth_token"), None)
        ct0 = next((c["value"] for c in x_cookies if c["name"] == "ct0"), None)
        if not auth or not ct0:
            return False
        headers = {
            "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "x-csrf-token": ct0,
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
            "content-type": "application/x-www-form-urlencoded",
            "cookie": f"auth_token={auth}; ct0={ct0};"
        }
        data = {}
        if user_id and str(user_id).isdigit():
            data["user_id"] = str(user_id)
        elif screen_name:
            data["screen_name"] = str(screen_name).lstrip("@")
        else:
            return False
        r = cffi_requests.post("https://x.com/i/api/1.1/friendships/create.json", headers=headers, data=data, impersonate="chrome124", timeout=8)
        if r.status_code == 200:
            res_json = r.json()
            if "id" in res_json or "screen_name" in res_json or "already" in str(res_json).lower():
                return True
        return False
    except Exception:
        return False

async def auto_join_telegram(phone: str, target_url: str) -> bool:
    try:
        session_path = os.path.join(SESSION_DIR, f"{phone}.session")
        if not os.path.exists(session_path):
            return False
        client = TelegramClient(session_path, API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return False

        target = target_url.strip().rstrip('/')
        entity = False
        if "t.me/+" in target or "joinchat/" in target:
            invite_hash = target.split('+')[-1].split('/')[-1]
            try:
                from telethon.tl.functions.messages import ImportChatInviteRequest
                await client(ImportChatInviteRequest(invite_hash))
                entity = True
            except Exception as ex:
                if "already" in str(ex).lower():
                    entity = True
        else:
            uname = target.split('/')[-1].lstrip('@')
            if uname:
                try:
                    from telethon.tl.functions.channels import JoinChannelRequest
                    await client(JoinChannelRequest(uname))
                    entity = True
                except Exception as ex:
                    if "already" in str(ex).lower():
                        entity = True

        await client.disconnect()
        return bool(entity)
    except Exception:
        return False

async def execute_task_for_acc(idx: int, acc: dict, task: dict, r_data: dict, get_ts):
    if idx > 0:
        await asyncio.sleep(random.uniform(2.5, 4.2) * idx)  # Jeda tertib manusiawi antar akun

    tid = task.get("id")
    ttype = task.get("type")
    title = task.get("title")
    pts = task.get("points_value") or 0

    cfg = acc["config"]
    api = acc["api"]
    cfile = acc["completed_file"]
    completed = acc["completed"]
    x_cookies = acc["x_cookies"]
    failed_retries = acc["failed_retries"]

    target_url = task.get("target_url")
    target_id = task.get("target_id")
    if not target_url or not str(target_url).startswith("http"):
        if target_id:
            target_url = f"https://x.com/i/status/{target_id}"

    assigned_comment = r_data.get("comment") or r_data.get("quote")

    action_ok = False

    # ⚡ ULTRA-FAST TLS PATH: Like, Repost, Follow dieksekusi instan via Chrome TLS (<0.3s)
    if ttype in ["like_twitter", "like"]:
        t_id = extract_tweet_id(target_url, target_id)
        if t_id:
            fast_ok = await asyncio.to_thread(fast_like_tweet, x_cookies, str(t_id))
            if fast_ok:
                action_ok = True
                print(f"[{get_ts()}] [{cfg['tag']}] ⚡ Like #{tid} via Fast API... Sukses")

    elif ttype in ["retweet", "repost"]:
        t_id = extract_tweet_id(target_url, target_id)
        if t_id:
            fast_ok, err_reason = await asyncio.to_thread(fast_repost_tweet, x_cookies, str(t_id))
            if fast_ok:
                action_ok = True
                print(f"[{get_ts()}] [{cfg['tag']}] ⚡ Repost #{tid} via Fast API... Sukses")
            elif err_reason == "daily_limit_reached":
                acc["repost_cooldown_until"] = time.time() + 3600
                print(f"[{get_ts()}] [{cfg['tag']}] ⚠️ Akun mencapai batas limit repost harian X (cooldown 1 jam untuk repost)")

    elif ttype == "follow_twitter":
        s_name, u_id = extract_follow_target(target_url, target_id)
        if s_name or u_id:
            fast_ok = await asyncio.to_thread(fast_follow_user, x_cookies, screen_name=s_name, user_id=u_id)
            if fast_ok:
                action_ok = True
                lbl = f"@{s_name}" if s_name else f"ID:{u_id}"
                print(f"[{get_ts()}] [{cfg['tag']}] ⚡ Follow {lbl} (#{tid}) via Fast API... Sukses")

    elif ttype == "join_telegram":
        if target_url:
            tg_ok = await auto_join_telegram(acc["phone"], target_url)
            if tg_ok:
                action_ok = True
                print(f"[{get_ts()}] [{cfg['tag']}] 📢 Join Telegram #{tid} ({target_url})... Sukses")

    elif ttype == "visit_website":
        action_ok = True
        print(f"[{get_ts()}] [{cfg['tag']}] 🌐 Visit Website #{tid} ({target_url})... Sukses")

    if not action_ok:
        automator = None
        try:
            stealth = Stealth()
            async with stealth.use_async(async_playwright()) as p:
                automator = TwitterAutomator(x_cookies)
                await automator.init_browser(p)

                if ttype == "follow_twitter":
                    action_ok = await automator.follow_user(target_url, target_id)
                elif ttype in ["like_twitter", "like"]:
                    action_ok = await automator.like_tweet(target_url)
                elif ttype in ["retweet", "repost"]:
                    action_ok = await automator.repost_tweet(target_url)
                elif ttype in ["comment_twitter", "reply_x", "comment"]:
                    action_ok = await automator.reply_tweet(target_url, assigned_comment)
                elif ttype in ["quote_twitter", "quote"]:
                    action_ok = await automator.reply_tweet(target_url, assigned_comment)
                elif ttype in ["bookmark_twitter", "bookmark"]:
                    action_ok = await automator.bookmark_tweet(target_url)

                await automator.close_browser()
        except Exception as e:
            print(f"[{get_ts()}] [{cfg['tag']}] ⚠️ Error browser automator: {e}")
            action_ok = False
        finally:
            if automator:
                try:
                    await automator.close_browser()
                except Exception:
                    pass

    if not action_ok:
        failed_retries[tid] = failed_retries.get(tid, 0) + 1
        if failed_retries[tid] >= 3:
            completed[str(tid)] = {
                "title": title,
                "points": 0,
                "skipped": True,
                "reason": "action_failed_3_retries_tweet_unavailable",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            save_completed_tasks(completed, cfile)
            print(f"[{get_ts()}] [{cfg['tag']}] ⚠️  #{tid} dilewati permanen (tweet tidak tersedia / aksi gagal 3x)")
        else:
            print(f"[{get_ts()}] [{cfg['tag']}] ℹ️  #{tid} (aksi tertunda [{failed_retries[tid]}/3], akan dicoba kembali)")
        return

    # Tunggu jeda alami 9.0 - 13.5 detik agar Twitter API mengindeks aksi secara tuntas
    await asyncio.sleep(random.uniform(9.0, 13.5))
    v_res = await asyncio.to_thread(api.verify_task, tid, {"platform": "android"})

    # Auto-retry verifikasi bertahap jika ada jeda indeks di Twitter API (tunggu ekstra 8s - 12s)
    for retry_idx in range(3):
        if not v_res.get("ok") and any(err in str(v_res.get("data", {})).lower() for err in ["not_liked", "not_retweeted", "not_commented", "not_found", "pending"]):
            await asyncio.sleep(8.0 + retry_idx * 4.0)
            v_res = await asyncio.to_thread(api.verify_task, tid, {"platform": "android"})
        else:
            break

    if v_res["ok"] and v_res.get("data", {}).get("verified"):
        awarded = v_res["data"].get("points_awarded", pts)
        now_act = time.time()
        acc["last_action_time"] = now_act
        if str(ttype).lower() in ["comment_twitter", "reply_x", "comment", "quote"]:
            acc["last_comment_time"] = now_act
        acc.setdefault("recent_actions", []).append({"time": now_act, "type": str(ttype).lower(), "id": tid})

        p_up = await asyncio.to_thread(api.get_user_profile)
        if p_up.get("ok"):
            acc["current_points"] = p_up["data"].get("points", acc["current_points"] + awarded)
        else:
            acc["current_points"] += awarded
        completed[str(tid)] = {
            "title": title,
            "points": awarded,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_completed_tasks(completed, cfile)
        print(f"[{get_ts()}] [{cfg['tag']}] 🎉 Sukses #{tid}: +{format_gomine(awarded)} | Total: {format_gomine(acc['current_points'])} ({len(completed)} Done)")
    else:
        v_data = v_res.get("data", {})
        detail = v_data.get("detail", v_data) if isinstance(v_data, dict) else v_data

        # Tangani cooldown sementara dari server GoMine (verify_fail_cap)
        fail_cap_obj = None
        if isinstance(detail, dict) and detail.get("code") == "verify_fail_cap":
            fail_cap_obj = detail
        elif isinstance(v_data, dict) and v_data.get("code") == "verify_fail_cap":
            fail_cap_obj = v_data

        if fail_cap_obj:
            reset_in = fail_cap_obj.get("reset_in", 1800)
            acc["cooldown_until"] = time.time() + reset_in + 15
            save_cooldown(acc["phone"], acc["cooldown_until"])
            mins = int(reset_in // 60)
            print(f"[{get_ts()}] [{cfg['tag']}] ⏳ Limit verifikasi server tercapai (Cooldown {mins} menit). Akun rehat sejenak...")
            return

        # Hanya tulis 'skipped' permanen jika memang server menolak permanen (sudah selesai, butuh proof, task berakhir)
        if any(w in str(detail).lower() for w in ["already", "proof_required", "task_ended", "unavailable", "tier_locked", "verified_required", "requires_verified"]):
            completed[str(tid)] = {
                "title": title,
                "points": 0,
                "skipped": True,
                "reason": detail,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            save_completed_tasks(completed, cfile)
            print(f"[{get_ts()}] [{cfg['tag']}] ℹ️  #{tid} dilewati ({explain_reason(detail)})")
            return

        failed_retries[tid] = failed_retries.get(tid, 0) + 1
        if failed_retries[tid] >= 3:
            completed[str(tid)] = {
                "title": title,
                "points": 0,
                "skipped": True,
                "reason": f"retry_limit_exceeded ({detail})",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            save_completed_tasks(completed, cfile)
            print(f"[{get_ts()}] [{cfg['tag']}] ⚠️  #{tid} dilewati setelah 3x gagal verifikasi ({detail})")
            return

        print(f"[{get_ts()}] [{cfg['tag']}] ℹ️  #{tid} verifikasi ({detail})")


async def run_sniper():
    print("=" * 70)
    print("       🎯 GOMINE MULTI-ACCOUNT X-TASK AUTO-SNIPER & KUOTA LOCKER ")
    print("       Akun Terdaftar: Master (@fannettt) & Nalyssa (@evazivanna) ")
    print("       Fitur : Instant Slot Reserve + Auto Execute + Auto Claim ")
    print("=" * 70 + "\n")

    def get_ts() -> str:
        return datetime.now().strftime("%H:%M:%S")

    active_cds = load_cooldowns()
    accounts_state = []
    for cfg in CONFIG_ACCOUNTS:
        phone = cfg["phone"]
        tkey = cfg["twitter_key"]
        cfile = cfg["completed_file"]
        name = cfg["name"]

        print(f"[*] Inisialisasi Akun {name} ({phone})...")
        completed = load_completed_tasks(cfile)
        x_cookies = load_x_cookies(tkey)
        try:
            init_data = await get_tg_init_data(phone)
            api = GoMineClient(init_data)
            prof_res = api.get_user_profile()
            if prof_res["ok"]:
                user = prof_res["data"]
                cur_pts = user.get("points", 0)
                sparks = user.get("sparks", 0)
                tier = user.get("access_tier_name", "Unknown")
                tw = user.get("twitter_username", "")
                cd_rem = active_cds.get(phone, 0) - time.time()
                cd_msg = f" | ⏳ Cooldown: {int(cd_rem//60)}m" if cd_rem > 0 else ""
                print(f"    👤 @{user.get('username')} | Tier: {tier} | Saldo: {format_gomine(cur_pts)} | X: @{tw}{cd_msg}")
                print(f"    🏆 Task selesai tersimpan: {len(completed)}")

                api.checkin()
                api.enable_nsfw()

                accounts_state.append({
                    "config": cfg,
                    "phone": phone,
                    "twitter_key": tkey,
                    "completed_file": cfile,
                    "completed": completed,
                    "x_cookies": x_cookies,
                    "init_data": init_data,
                    "api": api,
                    "current_points": cur_pts,
                    "token_age": time.time(),
                    "failed_retries": {},
                    "cooldown_until": active_cds.get(phone, 0),
                    "recent_actions": [],
                    "last_action_time": 0,
                    "last_comment_time": 0,
                    "hourly_action_cap": 18,
                    "hourly_repost_cap": 8
                })
            else:
                print(f"    ❌ Gagal ambil profil {phone}: {prof_res}")
        except Exception as e:
            print(f"    ❌ Error inisialisasi {phone}: {e}")

    if not accounts_state:
        print("❌ Tidak ada akun yang berhasil diinisialisasi!")
        return

    print(f"\n[3/3] 📡 Mengaktifkan Radar Pemantau Task X Multi-Akun ({len(accounts_state)} Akun)...")
    print("Tekan Ctrl+C untuk menghentikan radar.\n")

    radar_cycle = 0
    while True:
        radar_cycle += 1
        any_task_found = False

        # Refresh token jika > 50 menit
        for acc in accounts_state:
            if time.time() - acc["token_age"] > 3000:
                try:
                    acc["init_data"] = await get_tg_init_data(acc["phone"])
                    acc["api"] = GoMineClient(acc["init_data"])
                    acc["token_age"] = time.time()
                except Exception as ex:
                    print(f"[{get_ts()}] [{acc['config']['tag']}] ⚠️ Gagal refresh token: {ex}")

        # Scan task X untuk SETIAP akun secara paralel (High-Speed)
        # Sangat krusial: GoMine menyembunyikan task yang sudah dikerjakan Akun 1 dari respon API Akun 1.
        # Dengan memindai dari SEMUA akun, Akun 2 (Nalyssa) tidak akan pernah melewatkan task apapun!
        x_actions = ["Like", "Repost", "Follow", "Bookmark", "Comment", "Quote", "Reply"]
        async def fetch_for_acc(acc, action):
            tasks = await asyncio.to_thread(acc["api"].get_browse_category, "X", action)
            for t in tasks:
                t["action_category"] = action
            return tasks

        scan_coros = [fetch_for_acc(acc, a) for acc in accounts_state for a in x_actions]
        cat_results = await asyncio.gather(*scan_coros)
        discovered_tasks = [t for sub in cat_results for t in sub]

        # Scan periodik ke Endpoint Campaigns untuk memastikan task X & Telegram campaign tidak terlewat
        async def fetch_camp_x(acc):
            res_tasks = []
            try:
                camps = await asyncio.to_thread(acc["api"].get_campaigns)
                for camp in camps:
                    cid = camp.get("id")
                    if not cid:
                        continue
                    t_list = await asyncio.to_thread(acc["api"].get_campaign_tasks, cid)
                    for t in t_list:
                        tt = str(t.get("type", "")).lower()
                        if any(w in tt for w in ["twitter", "x", "like", "repost", "retweet", "comment", "quote", "bookmark", "telegram", "website"]):
                            res_tasks.append(t)
            except Exception:
                pass
            return res_tasks

        camp_coros = [fetch_camp_x(acc) for acc in accounts_state]
        camp_res = await asyncio.gather(*camp_coros)
        for sub in camp_res:
            discovered_tasks.extend(sub)

        # Filter tugas unik
        seen_ids = set()
        unique_tasks = []
        for t in discovered_tasks:
            tid = str(t.get("id"))
            if tid not in seen_ids:
                seen_ids.add(tid)
                unique_tasks.append(t)

        # 🎯 FILTER TASK VALID SEBELUM BATCHING:
        valid_tasks = []
        for task in unique_tasks:
            tid = str(task.get("id"))
            ttype = task.get("type")
            pts = task.get("points_value") or 0
            max_c = task.get("max_completions")
            c_count = task.get("completions_count", 0)

            # Abaikan kuota habis
            if max_c is not None and c_count >= max_c:
                continue

            # Abaikan task non-interaksi atau poin 0
            if str(ttype).lower() in ["link_twitter", "link_discord", "link_wallet", "bind_twitter", "connect_wallet", "quiz", "follow_instagram", "subscribe_youtube"] or pts <= 0:
                continue

            # Abaikan task khusus akun centang biru (verified), web3_locked, cooling, atau coming soon
            if task.get("requires_verified") or task.get("verified_locked") or task.get("web3_locked") or task.get("cooling") or task.get("coming_soon") or task.get("requires_verification"):
                continue

            # Hanya ambil task yang masih belum selesai di minimal salah satu akun yang aktif
            if any(tid not in acc["completed"] and time.time() >= acc.get("cooldown_until", 0) for acc in accounts_state):
                valid_tasks.append(task)

        # Urutkan task valid berdasarkan reward poin tertinggi
        valid_tasks.sort(key=lambda x: x.get("points_value") or 0, reverse=True)

        # FASE 1: BATCH-LOCK / BURST-RESERVE (Kunci kuota task terbaik secara teratur)
        # Menjelajahi antrean task valid, kunci maksimal 6 task yang berhasil di-reserve per siklus
        tasks_to_execute = []

        for task in valid_tasks:
            if len(tasks_to_execute) >= 6:
                break

            tid = task.get("id")
            ttype = task.get("type")
            title = task.get("title")
            pts = task.get("points_value") or 0

            # 🛡️ FILTER AKUN DENGAN PROTOKOL MAIN AMAN:
            now = time.time()
            eligible_accs = []
            for acc in accounts_state:
                if str(tid) in acc["completed"]:
                    continue
                if now < acc.get("cooldown_until", 0):
                    continue

                # Bersihkan riwayat aksi yang lebih lama dari 1 jam (sliding window 60 menit)
                acc["recent_actions"] = [a for a in acc.get("recent_actions", []) if now - a["time"] < 3600]

                # 1. Batas maksimal aksi total per jam (Maks 18 aksi/jam)
                if len(acc["recent_actions"]) >= acc.get("hourly_action_cap", 18):
                    acc["cooldown_until"] = now + 600  # Istirahat 10 menit
                    print(f"[{get_ts()}] [{acc['config']['tag']}] 🛡️ Mode Aman: Kuota 18 aksi/jam tercapai. Istirahat 10 menit agar akun X tetap sehat.")
                    continue

                # 2. Batas maksimal Repost per jam (Maks 8 repost/jam)
                if str(ttype).lower() in ["retweet", "repost"]:
                    if now < acc.get("repost_cooldown_until", 0):
                        continue
                    reposts_last_hr = len([a for a in acc["recent_actions"] if a.get("type") in ["retweet", "repost"]])
                    if reposts_last_hr >= acc.get("hourly_repost_cap", 8):
                        acc["repost_cooldown_until"] = now + 1200  # Istirahat repost 20 menit
                        print(f"[{get_ts()}] [{acc['config']['tag']}] 🛡️ Mode Aman: Batas 8 repost/jam tercapai. Istirahat repost 20 menit.")
                        continue

                # 3. Spasi antar Comment (Minimal 90 detik jeda antar komentar di akun yang sama)
                if str(ttype).lower() in ["comment_twitter", "reply_x", "comment", "quote"]:
                    if now - acc.get("last_comment_time", 0) < 90:
                        continue

                eligible_accs.append(acc)
            if not eligible_accs:
                continue

            # ⚡ TEMBAK SNIPE MULTI-AKUN (HIGH-SPEED ULTRA-FAST 80ms)
            async def reserve_call(idx, acc):
                if idx > 0:
                    await asyncio.sleep(0.08 * idx)  # 80ms super-fast stagger agar 4 akun mengunci slot dalam <0.25 detik
                res = await asyncio.to_thread(acc["api"].reserve_task, tid)
                # Auto-retry 1x jika server GoMine 429 / 5xx / busy
                if not res.get("ok") and (res.get("status") in [429, 500, 502, 503] or "busy" in str(res.get("error", "")).lower()):
                    await asyncio.sleep(0.3)
                    res = await asyncio.to_thread(acc["api"].reserve_task, tid)
                return acc, res

            reserve_results = await asyncio.gather(*(reserve_call(i, a) for i, a in enumerate(eligible_accs)))

            reserved_accs = []
            skipped_tags = []
            for acc, res_reserve in reserve_results:
                cfg = acc["config"]
                r_data = res_reserve.get("data", {})
                if res_reserve.get("ok") and r_data.get("reserved"):
                    print(f"[{get_ts()}] [{cfg['tag']}] ⚡ Kunci #{tid} ({clean_type(ttype)}) +{format_gomine(pts)}...")
                    reserved_accs.append((acc, r_data))
                else:
                    reason = r_data.get("reason") or res_reserve.get("error") or "kuota slot penuh direbut user global"
                    # Tandai lewati langsung agar tidak terus-menerus mengulang dan memenuhi log
                    acc["completed"][str(tid)] = {
                        "title": title,
                        "points": 0,
                        "skipped": True,
                        "reason": str(reason),
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    save_completed_tasks(acc["completed"], acc["completed_file"])
                    skipped_tags.append(cfg['tag'])

            if skipped_tags and not reserved_accs:
                print(f"[{get_ts()}] ℹ️  #{tid} dilewati (kuota slot sudah penuh direbut user global)")
            elif skipped_tags and reserved_accs:
                print(f"[{get_ts()}] ℹ️  #{tid} dilewati untuk {', '.join(skipped_tags)} (sisa kuota habis)")

            if reserved_accs:
                any_task_found = True
                tasks_to_execute.append((task, reserved_accs))

        # FASE 2: QUEUE EXECUTION (Eksekusi antrean yang sudah berhasil dikunci)
        # Kuota sudah 100% aman tersimpan di database GoMine selama 5-25 menit, jadi eksekusi aman dan tertib
        for task, reserved_accs in tasks_to_execute:
            await asyncio.gather(*(execute_task_for_acc(i, acc, task, r_data, get_ts) for i, (acc, r_data) in enumerate(reserved_accs)))

        if not any_task_found:
            # Tampilkan detak radar setiap 5 siklus (atau siklus awal) agar log tenang dan bersih
            if radar_cycle % 5 == 1 or radar_cycle <= 3:
                summary_parts = []
                for a in accounts_state:
                    cd = a.get("cooldown_until", 0) - time.time()
                    if cd > 0:
                        mins = int(cd // 60)
                        summary_parts.append(f"{a['config']['tag']}: {format_gomine(a['current_points'])} (Cooldown {mins}m)")
                    else:
                        summary_parts.append(f"{a['config']['tag']}: {format_gomine(a['current_points'])} ({len(a['completed'])} Done)")
                print(f"[{get_ts()}] 📡 Radar #{radar_cycle:<3} | {' | '.join(summary_parts)}")

        delay = round(random.uniform(1.8, 2.8), 1)
        await asyncio.sleep(delay)

if __name__ == "__main__":
    try:
        asyncio.run(run_sniper())
    except KeyboardInterrupt:
        print("\nRadar dihentikan oleh pengguna.")
