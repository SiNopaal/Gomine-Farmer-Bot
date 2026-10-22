# 🚜 GoMine Multi-Account Automation & X-Task Sniper Bot

Bot otomatisasi canggih multi-akun untuk **GoMine Telegram Mini App** (`app.gomine.social`), dilengkapi dengan fitur **High-Speed Multi-Account X-Task Sniper** (Like, Repost, Follow, Comment) dengan sistem **Instant Slot Locking (80ms)**, TLS Fingerprint Chrome 124, dan Playwright Stealth.

---

## 🌟 Fitur Utama

### 1. ⚡ High-Speed Multi-Account X-Task Sniper (`x_task_sniper.py`)
* **Instant Slot Reservation (80ms Micro-Stagger)**: Mengunci kuota campaign baru dari advertiser GoMine serentak untuk seluruh akun dalam <0.25 detik sebelum kuota direbut bot global lain.
* **Dual Execution Engine**:
  * **Ultra-Fast Chrome TLS Path (`curl_cffi`)**: Eksekusi Like, Repost, dan Follow instan (<0.3s) menggunakan JA3/JA4 fingerprint Chrome 124 asli tanpa membuka browser.
  * **Stealth Playwright Engine**: Eksekusi Comment/Reply dan Quote menggunakan browser Chrome dengan modul `playwright_stealth` anti-freeze.
* **Auto Daily Retweet Limit Protection**: Mendeteksi batas limit harian Twitter/X (`error 344 / daily limit`) dan otomatis mengaktifkan cooldown istirahat 1 jam per akun.
* **Smart Radar**: Polling radar adaptif 1.8 – 2.8 detik dengan rangkuman status saldo real-time.

### 2. 🌾 Multi-Account Telegram Farmer (`bot.py`)
* **Auto Daily Check-in**: Klaim bonus harian streak.
* **Auto Mining Claim & Boost**: Otomatis klaim hasil tambang GOMINE dan upgrade level boost saat poin mencukupi.
* **Auto Telegram Tasks**: Otomatis join channel/grup Telegram dan verifikasi reward.
* **Auto Launch Campaign Tasks**: Verifikasi task web/miniapp partner.
* **Anti-Ban Device Fingerprinting**: Setiap sesi Telegram disimulasikan menggunakan model perangkat Android unik (Pixel, Galaxy, Xiaomi, dll) agar terhindar dari deteksi multi-akun.

---

## 📁 Struktur Direktori

```text
gomine-farmer-bot/
├── bot.py                     # Telegram farming worker (Checkin, Claim, Boost, TG tasks)
├── x_task_sniper.py           # Multi-account high-speed X/Twitter task sniper
├── config.example.json        # Template konfigurasi bot farming
├── accounts_config.example.json # Template multi-akun untuk sniper
├── accounts.example.json      # Template cookie auth_token & ct0 Twitter
├── run.bat                    # Script cepat menjalankan bot farming
├── run_x_sniper.bat           # Script cepat menjalankan x_task_sniper
├── requirements.txt           # Dependensi Python
└── README.md                  # Dokumentasi panduan
```

---

## ⚙️ Persyaratan Sistem

* **Python 3.10+**
* File sesi Telegram (`.session`) dari Telethon
* Cookie akun X/Twitter (`auth_token` & `ct0`)

---

## 🚀 Panduan Instalasi & Menjalankan

### 1. Clone Repositori
```bash
git clone https://github.com/SiNopaal/Gomine-Farmer-Bot.git
cd Gomine-Farmer-Bot
```

### 2. Install Dependensi
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Konfigurasi Akun

1. **Konfigurasi Farming (`config.json`)**:
   Salin `config.example.json` menjadi `config.json`:
   ```bash
   cp config.example.json config.json
   ```
   Sesuaikan `main_account_phone` dan letak folder `telegram_session_dir`.

2. **Konfigurasi Sniper Multi-Akun (`accounts_config.json`)**:
   Salin `accounts_config.example.json` menjadi `accounts_config.json`:
   ```bash
   cp accounts_config.example.json accounts_config.json
   ```
   Isi nomor HP Telegram dan mapping `twitter_key` untuk masing-masing akun.

3. **Konfigurasi Cookie Twitter (`accounts.json`)**:
   Salin `accounts.example.json` menjadi `accounts.json`:
   ```bash
   cp accounts.example.json accounts.json
   ```
   Masukkan `auth_token` dan `ct0` dari browser kamu (didapat dari DevTools -> Application -> Cookies -> `https://x.com`).

---

## 🎮 Cara Menjalankan

### Menjalankan X-Task Sniper (Rekomendasi untuk Cuan Cepat)
```bash
python x_task_sniper.py
```
*atau klik dua kali file `run_x_sniper.bat` di Windows.*

### Menjalankan Telegram Farmer (Daily Check-in & Mining)
```bash
python bot.py
```
*atau klik dua kali file `run.bat` di Windows.*

---

## ⚠️ Disclaimer
Script ini dibuat untuk tujuan edukasi dan automasi pribadi. Penggunaan script sepenuhnya merupakan tanggung jawab pengguna. Pastikan selalu menggunakan jeda yang wajar agar akun tetap aman.
