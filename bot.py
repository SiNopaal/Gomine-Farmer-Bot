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
from typing import Dict, Any, List, Optional, Tuple
import requests
from telethon import TelegramClient
from telethon.tl.functions.messages import RequestAppWebViewRequest, ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import InputBotAppShortName
from telethon.errors import FloodWaitError, UserDeactivatedError, AuthKeyUnregisteredError

# UTF-8 stdout configuration for Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
HISTORY_PATH = os.path.join(os.path.dirname(__file__), "farm_history.json")

def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_history() -> Dict[str, Any]:
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_history(history: Dict[str, Any]):
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"   [WARN] Gagal menyimpan riwayat: {e}")

def get_client_fingerprint(session_filename: str) -> Dict[str, str]:
    h = int(hashlib.md5(session_filename.encode("utf-8")).hexdigest(), 16)
    app_versions = ["10.14.5 (4890)", "10.14.4 (4880)", "10.14.3 (4870)"]
    system_versions = ["Android 12 (SDK 31)", "Android 13 (SDK 33)", "Android 14 (SDK 34)"]
    device_models = ["Google Pixel 6", "Samsung Galaxy S22", "Xiaomi 12", "OnePlus 9", "Vivo X80"]

    app_ver = app_versions[h % len(app_versions)]
    sys_ver = system_versions[(h >> 2) % len(system_versions)]
    dev_model = device_models[(h >> 4) % len(device_models)]

    clean_name = session_filename.replace("+", "")
    if clean_name.startswith("62"):
        lang = "id"
        sys_lang = "id-ID"
    else:
        lang = "en"
        sys_lang = "en-US"

    return {
        "device_model": dev_model,
        "system_version": sys_ver,
        "app_version": app_ver,
        "lang_code": lang,
        "system_lang_code": sys_lang
    }

async def extract_gomine_auth_and_join_channels(
    session_path: str,
    api_id: int,
    api_hash: str,
    master_ref: str,
    auto_join_channels: bool = True
) -> Tuple[Optional[str], List[str]]:
    fname = os.path.basename(session_path)
    fp = get_client_fingerprint(fname)
    joined_log = []

    client = TelegramClient(
        session_path,
        api_id,
        api_hash,
        device_model=fp["device_model"],
        system_version=fp["system_version"],
        app_version=fp["app_version"],
        lang_code=fp["lang_code"],
        system_lang_code=fp["system_lang_code"]
    )

    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return "UNAUTHORIZED", []

        # 1. Join Target Channels for Launch Campaign Tasks
        if auto_join_channels:
            # Public channels/groups
            for target in ["GoMineOfficial", "GoMineCommunity", "GoMineInIndonesian"]:
                try:
                    ch = await client.get_entity(target)
                    await client(JoinChannelRequest(ch))
                    joined_log.append(f"@{target}")
                except Exception:
                    pass

            # Private invite channel (GoMine Task Alerts)
            try:
                await client(ImportChatInviteRequest("_4aYhiMdys9iN2Jh"))
                joined_log.append("TaskAlerts")
            except Exception:
                pass

        # 2. Extract WebApp Auth URL
        bot = await client.get_input_entity("GoMineAppBot")
        app = InputBotAppShortName(bot_id=bot, short_name="app")
        
        start_param = f"ref_{master_ref}" if master_ref else ""
        res = await client(RequestAppWebViewRequest(
            peer=bot,
            app=app,
            platform="android",
            start_param=start_param
        ))
        await client.disconnect()

        raw_url = res.url
        frag = raw_url.split('#', 1)[-1]
        params = urllib.parse.parse_qs(frag)
        init_data = params.get("tgWebAppData", [""])[0]
        return (init_data if init_data else None), joined_log

    except FloodWaitError as e:
        print(f"      ⏳ [FLOOD_WAIT] Telegram cooldown {e.seconds}s.")
        await asyncio.sleep(min(e.seconds, 15))
        try: await client.disconnect()
        except Exception: pass
        return None, []
    except (UserDeactivatedError, AuthKeyUnregisteredError):
        try: await client.disconnect()
        except Exception: pass
        return "EXPIRED", []
    except Exception as e:
        print(f"      ❌ [TELEGRAM_ERR] {e}")
        try: await client.disconnect()
        except Exception: pass
        return None, []

class GoMineAPI:
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
            r = self.session.request(method, url, json=json_data, params=params, headers=hdrs, timeout=15)
            try:
                res_json = r.json()
            except Exception:
                res_json = {"raw": r.text}
            return {"status_code": r.status_code, "ok": (200 <= r.status_code < 300), "data": res_json}
        except Exception as e:
            return {"status_code": 0, "ok": False, "error": str(e)}

    def init_user(self, username: str, first_name: str, ref_code: str) -> Dict[str, Any]:
        payload = {
            "username": username,
            "first_name": first_name,
            "ref": ref_code,
            "platform": "android",
            "boot_reason": "first_open"
        }
        return self._call("POST", "/users/init", json_data=payload, params={"tz_offset": 420})

    def checkin(self) -> Dict[str, Any]:
        return self._call("POST", "/users/checkin")

    def get_mining(self) -> Dict[str, Any]:
        return self._call("GET", "/sparks/mining")

    def boost_mining(self) -> Dict[str, Any]:
        return self._call("POST", "/sparks/mining/boost")

    def claim_mining(self) -> Dict[str, Any]:
        return self._call("POST", "/sparks/mining/claim")

    def get_friends(self) -> Dict[str, Any]:
        return self._call("GET", "/sparks/friends")

    def claim_referrals(self) -> Dict[str, Any]:
        return self._call("POST", "/sparks/referral/claim")

    def ensure_task_session(self) -> bool:
        """Mengambil session token & HMAC secret untuk verifikasi tasks."""
        if self.session_data:
            return True
        r = self._call("POST", "/users/session-init")
        if r["ok"] and isinstance(r["data"], dict) and "secret" in r["data"]:
            self.session_data = r["data"]
            srv_now = r["data"].get("now", time.time())
            self.time_offset = srv_now * 1000 - time.time() * 1000
            return True
        return False

    def get_signed_task_headers(self, method: str = "POST") -> Dict[str, str]:
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

    def get_campaign_tasks(self, campaign_id: int = 1) -> List[Dict[str, Any]]:
        r = self._call("GET", f"/campaigns/{campaign_id}/tasks")
        if r["ok"] and isinstance(r["data"], list):
            return r["data"]
        return []

    def reserve_task(self, task_id: int) -> Dict[str, Any]:
        hdrs = self.get_signed_task_headers("POST")
        return self._call("POST", f"/tasks/{task_id}/reserve", custom_headers=hdrs)

    def verify_task(self, task_id: int, payload: Optional[Dict] = None) -> Dict[str, Any]:
        hdrs = self.get_signed_task_headers("POST")
        p = payload if payload is not None else {"platform": "android"}
        return self._call("POST", f"/tasks/{task_id}/verify", json_data=p, custom_headers=hdrs)

def run_account_cycle(session_path: str, is_main: bool, config: Dict[str, Any], history: Dict[str, Any]):
    phone_name = os.path.basename(session_path).replace(".session", "")
    role_label = "👑 [AKUN UTAMA]" if is_main else "🚀 [SUB-AKUN]"
    master_ref = config["master_referral_code"]

    print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"{role_label} Memproses Akun: {phone_name}")

    # 1. Ekstrak Auth & Auto Join Channel Telegram
    print("   🔑 [AUTH] Menghubungkan ke Telegram & Auto-Join Channel GoMine...")
    tg_data, joined_channels = asyncio.run(extract_gomine_auth_and_join_channels(
        session_path,
        config["api_id"],
        config["api_hash"],
        master_ref,
        auto_join_channels=config["features"].get("auto_complete_telegram_tasks", True)
    ))

    if tg_data in ("EXPIRED", "UNAUTHORIZED"):
        print(f"   ❌ [AUTH] Sesi {phone_name} invalid / expired di Telegram.")
        history[phone_name] = {"last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "status": "EXPIRED"}
        save_history(history)
        return
    elif not tg_data:
        print(f"   ⚠️ [AUTH] Gagal mendapatkan tgWebAppData untuk {phone_name}.")
        return

    if joined_channels:
        print(f"   📢 [TELEGRAM] Sukses bergabung ke: {', '.join(joined_channels)}")

    print("   ✅ [AUTH] Token WebApp berhasil diamankan!")
    time.sleep(random.uniform(config["action_delay_min_sec"], config["action_delay_max_sec"]))

    # Parse telegram user info
    try:
        user_str = urllib.parse.parse_qs(tg_data).get("user", ["{}"])[0]
        tg_user = json.loads(user_str)
        username = tg_user.get("username", "")
        first_name = tg_user.get("first_name", phone_name)
    except Exception:
        username = ""
        first_name = phone_name

    api = GoMineAPI(tg_data)

    # 2. Init User / Bind Reff
    print(f"   🌐 [INIT] Sinkronisasi akun ke GoMine (Ref: {master_ref})...")
    
    while True:
        init_res = api.init_user(username, first_name, master_ref)
        
        if init_res["status_code"] == 429:
            detail = init_res.get("data", {}).get("detail", "Too many accounts from this network recently.")
            print(f"   ⚠️ [LIMIT IP] Server GoMine membatasi pendaftaran IP untuk {phone_name}: {detail}")
            history[phone_name] = {
                "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "IP_RATE_LIMITED",
                "note": detail
            }
            save_history(history)
            return
        elif not init_res["ok"]:
            err_msg = init_res.get("data", {}).get("detail", init_res.get("error", "Init failed"))
            print(f"   ❌ [INIT_ERR] Gagal init: {err_msg}")
            return
        else:
            break

    u_data = init_res["data"]
    uid = u_data.get("id")
    uname = u_data.get("username") or phone_name
    tier_name = u_data.get("access_tier_name", "Standard")
    points = u_data.get("points", 0)
    sparks = u_data.get("sparks", 0)
    streak = u_data.get("streak_days", 0)
    checked_in = u_data.get("checked_in_today", False)

    print(f"   👤 [USER] @{uname} (ID: {uid}) | Tier: {tier_name} | Saldo: {points} GOMINE | GTF: {sparks}")

    # 3. Selesaikan Task Launch Campaign (Fokus GOMINE Points & Grup Telegram)
    total_task_pts = 0
    if config["features"].get("auto_complete_launch_campaign", True):
        print("   🎯 [TASKS] Memeriksa tugas 'Launch Campaign' (Poin GOMINE & Telegram)...")
        tasks = api.get_campaign_tasks(campaign_id=1)
        if tasks:
            for t in tasks:
                tid = t.get("id")
                ttype = t.get("type")
                ttitle = t.get("title", f"Task #{tid}")
                tpts = t.get("points_value", 0)
                is_verified = t.get("verified", False)

                # Prioritas: Tugas Join Telegram, Visit Website, dan Quiz
                if not is_verified and ttype in ["join_telegram", "visit_website", "quiz"]:
                    print(f"      📌 Menjalankan Task #{tid}: '{ttitle}' (+{tpts} GOMINE)...")
                    # Step 1: Reserve
                    api.reserve_task(tid)
                    time.sleep(random.uniform(1.0, 1.8))

                    # Step 2: Verify
                    payload = {"platform": "android"}
                    if ttype == "quiz" and tid == 7806:
                        payload["answer"] = "1$"
                    v_res = api.verify_task(tid, payload)
                    if v_res["ok"] and v_res["data"].get("verified"):
                        awarded = v_res["data"].get("points_awarded", tpts)
                        total_task_pts += awarded
                        print(f"      ✅ [SUKSES] Task #{tid} TERVERIFIKASI! (+{awarded} GOMINE)")
                    else:
                        detail = v_res.get("data", {}).get("detail", "Pending")
                        print(f"      ℹ️ Task #{tid}: {detail}")
                    time.sleep(random.uniform(config["action_delay_min_sec"], config["action_delay_max_sec"]))
        else:
            print("   ℹ️ Tidak ada tugas aktif di Launch Campaign.")

    # 4. Daily Check-in
    if config["features"].get("auto_daily_checkin", True):
        time.sleep(random.uniform(config["action_delay_min_sec"], config["action_delay_max_sec"]))
        if checked_in:
            print("   ✅ [CHECKIN] Absen harian sudah selesai.")
        else:
            c_res = api.checkin()
            if c_res["ok"]:
                awarded = c_res["data"].get("sparks_awarded", 0)
                print(f"   🎉 [CHECKIN] Sukses klaim absen harian: +{awarded} GTF")
            elif c_res.get("data", {}).get("detail") == "already_checked_in":
                print("   ✅ [CHECKIN] Sudah check-in hari ini.")

    # 5. Mining Boost & Claim
    if config["features"].get("auto_mining_boost", True):
        api.boost_mining()
    if config["features"].get("auto_mining_claim", True):
        cl_res = api.claim_mining()
        if cl_res["ok"]:
            cl_val = cl_res["data"].get("claimed", 0)
            if cl_val > 0:
                print(f"   ⛏️ [MINING] Berhasil klaim +{cl_val} GTF dari mining bucket.")

    # 6. Khusus Akun Utama: Panen Referral Rewards
    if is_main and config["features"].get("auto_claim_referral_rewards", True):
        time.sleep(random.uniform(config["action_delay_min_sec"], config["action_delay_max_sec"]))
        print("   🎁 [HARVEST] Memeriksa saldo bonus referral akun utama...")
        fr_res = api.get_friends()
        if fr_res["ok"]:
            fr_data = fr_res["data"]
            total_fr = fr_data.get("total", 0)
            claimable = fr_data.get("claimable", 0)
            print(f"   👥 [REFF STATS] Total Teman Aktif: {total_fr} | Bonus Claimable: {claimable} GTF")
            if claimable > 0:
                rc_res = api.claim_referrals()
                if rc_res["ok"]:
                    print(f"   🎉 [REFF_SUCCESS] Berhasil klaim referral: +{rc_res['data'].get('claimed', 0)} GTF!")

    final_points = points + total_task_pts
    print(f"   💰 [SALDO AKHIR] Total Poin: {final_points} GOMINE")

    history[phone_name] = {
        "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "role": "MAIN" if is_main else "SUB",
        "username": uname,
        "points": final_points,
        "tasks_completed_this_run": total_task_pts,
        "status": "SUCCESS"
    }
    save_history(history)

def main():
    print("=" * 70)
    print("     ⛏️  GOMINE AUTO-FARMER & LAUNCH CAMPAIGN TASK BOT         ")
    print("=" * 70)

    config = load_config()
    history = load_history()

    base_dir = os.path.dirname(__file__)
    session_dir = os.path.normpath(os.path.join(base_dir, config["telegram_session_dir"]))

    if not os.path.exists(session_dir):
        print(f"❌ Direktori sesi tidak ditemukan: {session_dir}")
        return

    all_files = [f for f in os.listdir(session_dir) if f.endswith(".session")]
    main_phone = config.get("main_account_phone", "+6281227121848")

    sub_sessions = [os.path.join(session_dir, f) for f in all_files if not f.startswith(main_phone)]
    main_session = [os.path.join(session_dir, f) for f in all_files if f.startswith(main_phone)]

    unregistered = []
    already_success = []
    for s in sub_sessions:
        pname = os.path.basename(s).replace(".session", "")
        if history.get(pname, {}).get("status") == "SUCCESS":
            already_success.append(s)
        else:
            unregistered.append(s)

    # Prioritaskan akun yang belum terdaftar di urutan pertama
    sorted_sub_sessions = unregistered + already_success

    print(f"🎯 Master Referrer: {config['master_referral_code']}")
    print(f"📁 Ditemukan {len(sub_sessions)} Sub-Akun & {len(main_session)} Akun Utama")
    print(f"📊 Status Sub-Akun: {len(already_success)} SUDAH terdaftar | {len(unregistered)} BELUM terdaftar")
    print("=" * 70)

    # Tahap 1: Jalankan Seluruh Sub-Akun
    print("\n🚀 [TAHAP 1] Menjalankan sub-akun (Prioritas: yang belum terdaftar)...")
    for idx, s_path in enumerate(sorted_sub_sessions, 1):
        pname = os.path.basename(s_path).replace(".session", "")
        status_info = "⚡ [BARU / BELUM DAFTAR]" if pname not in history or history[pname].get("status") != "SUCCESS" else "✅ [SUDAH TERDAFTAR]"
        print(f"\n[Akun {idx}/{len(sorted_sub_sessions)}] - {pname} {status_info}")
        run_account_cycle(s_path, is_main=False, config=config, history=history)
        cd = random.uniform(config["account_delay_min_sec"], config["account_delay_max_sec"])
        print(f"   💤 [COOLDOWN] Menunggu {cd:.1f}s sebelum akun berikutnya...")
        time.sleep(cd)

    # Tahap 2: Jalankan Akun Utama untuk Panen Referral
    if main_session:
        print("\n" + "=" * 70)
        print("👑 [TAHAP 2] Menjalankan AKUN UTAMA untuk tasks, claim & panen reff!")
        print("=" * 70)
        run_account_cycle(main_session[0], is_main=True, config=config, history=history)

    print("\n" + "=" * 70)
    print("         🎉 SIKLUS GOMINE LAUNCH CAMPAIGN & FARMING SELESAI!      ")
    print("=" * 70)

if __name__ == "__main__":
    main()
