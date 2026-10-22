# 🎯 GoMine Multi-Account X-Task Auto-Sniper & Kuota Locker

Bot auto-sniper berkecepatan tinggi multi-akun untuk menyelesaikan seluruh tugas sosial **X / Twitter** (Like, Repost, Follow, Comment/Reply) pada **GoMine Telegram Mini App** (`app.gomine.social`).

Dilengkapi dengan sistem **Instant Slot Locking (80ms Micro-Stagger)**, **Dual Execution Engine (Chrome TLS + Playwright Stealth)**, serta proteksi keamanan akun X alami (*anti-ban & rate-limit auto-cooldown*).

---

## 🌟 Fitur Unggulan

### 1. ⚡ High-Speed Slot Locking (80ms Micro-Stagger)
* **Instant Kuota Reservation**: Mengunci kuota slot campaign baru dari advertiser dalam hitungan **<0.25 detik** serempak untuk seluruh akun terhubung sebelum direbut ribuan bot/user global lainnya.
* **Smart Radar Loop**: Polling radar adaptif 1.8 – 2.8 detik untuk mendeteksi campaign baru secara instan.
* **Auto Slot-Exhaustion Skip**: Melewati otomatis campaign kadaluarsa / kuota 0 tanpa pengulangan log yang memenuhi layar.

### 2. 🚀 Dual Execution Engine
* **Ultra-Fast Chrome TLS Path (`curl_cffi`)**:
  * Meniru persis sidik jari browser (*JA3/JA4 TLS handshake*) Chrome 124.
  * Mengeksekusi tugas **Like**, **Repost**, dan **Follow** instan (<0.3 detik) langsung ke API internal GraphQL X tanpa perlu merender browser berat.
* **Stealth Playwright Engine (`playwright_stealth`)**:
  * Mengeksekusi tugas **Comment / Reply**, **Quote**, dan **Bookmark** secara mulus.
  * Kebal deteksi headless crawler dan anti-freeze pada antarmuka web X.

### 3. 🛡️ Proteksi Anti-Ban & Auto-Cooldown
* **Deteksi Limit Harian X (`Error 344`)**: Jika akun mendekati batas harian retweet dari Twitter/X, bot otomatis mengaktifkan masa istirahat (cooldown) 1 jam khusus untuk repost, dan tetap aktif untuk like/follow.
* **Server Verify Cap Auto-Cooldown**: Membaca parameter cooldown resmi dari server GoMine (`verify_fail_cap`) jika limit verifikasi tercapai.
* **Micro-Stagger Execution**: Jeda mikro alami antar-akun agar tidak terjadi tabrakan permintaan dari IP yang sama.

---

## 📁 Struktur Repositori

```text
Gomine-Farmer-Bot/
├── x_task_sniper.py             # Script utama X-Task Auto-Sniper
├── accounts_config.example.json # Template konfigurasi daftar akun
├── accounts.example.json        # Template kredensial cookies Twitter (auth_token & ct0)
├── run_x_sniper.bat             # Script runner cepat untuk Windows
├── requirements.txt             # Dependensi Python
└── README.md                    # Dokumentasi lengkap
```

---

## ⚙️ Persyaratan Sistem

* **Python 3.10 atau lebih baru**
* Google Chrome terinstall di sistem
* File sesi Telegram (`.session`) untuk masing-masing akun
* Cookie login akun X (`auth_token` & `ct0`)

---

## 🚀 Panduan Instalasi & Penggunaan

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

1. **Konfigurasi Akun Sniper (`accounts_config.json`)**:
   Salin `accounts_config.example.json` menjadi `accounts_config.json`:
   ```bash
   cp accounts_config.example.json accounts_config.json
   ```
   Isi nomor HP Telegram, tag, dan nama akun:
   ```json
   [
     {
       "phone": "+6281234567890",
       "twitter_key": "account1",
       "name": "Master",
       "tag": "👑 Master",
       "completed_file": "completed_x_tasks.json"
     }
   ]
   ```

2. **Konfigurasi Cookie Twitter (`accounts.json`)**:
   Salin `accounts.example.json` menjadi `accounts.json`:
   ```bash
   cp accounts.example.json accounts.json
   ```
   Masukkan `auth_token` dan `ct0` dari browser kamu:
   ```json
   {
     "accounts": {
       "account1": {
         "auth_token": "YOUR_AUTH_TOKEN",
         "ct0": "YOUR_CT0"
       }
     }
   }
   ```
   *(Tips: Ambil nilai `auth_token` dan `ct0` dari menu Inspect Element (F12) -> Application -> Cookies -> https://x.com).*

3. **Pastikan Sesi Telegram Tersedia**:
   Pastikan file `.session` yang sesuai dengan nomor HP berada di folder sesi Telegram kamu.

---

## 🎮 Cara Menjalankan

Jalankan sniper menggunakan perintah:
```bash
python x_task_sniper.py
```
*atau cukup klik dua kali pada file `run_x_sniper.bat` di Windows.*

---

## ⚠️ Disclaimer
Proyek ini dibuat untuk tujuan riset, edukasi, dan automasi pribadi. Segala risiko penggunaan terhadap akun pengguna berada di bawah tanggung jawab masing-masing.
