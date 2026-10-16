#!/usr/bin/env python3
"""
Voratoon Automated Account Creator via CapSolver API
----------------------------------------------------
- 100% Headless di VPS (Tanpa Browser, Tanpa GUI, Tanpa Playwright)
- Menggunakan CapSolver AntiTurnstileTaskProxyLess untuk memecahkan Cloudflare Turnstile
- 13 Domain TempMail bervariasi dari mail.taveve.my.id
- Full Nama Asli Jepang (Romaji / Alfabet)
- Otomatis mendaftar, login, dan menyimpan token ke .env VPS!
"""

import sys
import os
import time
import json
import random
import urllib.request
import urllib.error

API_BASE = "https://api.voratoon.com"
TMAIL_URL = "https://mail.taveve.my.id"
SITE_KEY = "0x4AAAAAAEOmIHqZQLQ6GPRc"
SITE_URL = "https://v8.voratoon.com/auth"

DOMAINS_POOL = [
    "onlytaveve.biz.id", "onlytaveve.my.id", "tavevestr.web.id", "tavevestr.my.id",
    "taveve.my.id", "taveve.web.id", "amtaveve.my.id", "amtaveve.web.id",
    "amtaveve.biz.id", "tavevestore.web.id", "tavevestore.biz.id", "nyawitkeun.my.id",
    "tavevejaya.my.id"
]

FIRST_NAMES = [
    "Haruto", "Yuto", "Sota", "Yuki", "Hayato", "Ryota", "Sora", "Ren",
    "Kaito", "Kazuki", "Takumi", "Shota", "Daiki", "Kenta", "Riku", "Tsubasa",
    "Aoi", "Hinata", "Yuma", "Taiki", "Shin", "Kota", "Keita", "Kenji",
    "Makoto", "Tatsuya", "Naoki", "Ryusei", "Shohei", "Kouta", "Daichi",
    "Akira", "Ryoma", "Sosuke", "Itsuki", "Asahi", "Yusei", "Minato", "Reo"
]

LAST_NAMES = [
    "Sato", "Suzuki", "Takahashi", "Tanaka", "Watanabe", "Ito", "Yamamoto",
    "Nakamura", "Kobayashi", "Kato", "Yoshida", "Yamada", "Sasaki", "Yamaguchi",
    "Saito", "Matsumoto", "Inoue", "Kimura", "Hayashi", "Shimizu", "Yamazaki"
]

def generate_japanese_identity():
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    full_name = f"{first} {last}"
    rand_num = random.randint(10, 999)
    username = f"{first.lower()}_{last.lower()}{rand_num}"
    password = f"K0m1k@{random.randint(1000, 9999)}!"
    return full_name, username, password

def generate_temp_email(username: str, used_domains: list) -> str:
    available = [d for d in DOMAINS_POOL if d not in used_domains]
    if not available:
        available = DOMAINS_POOL
    domain = random.choice(available)
    used_domains.append(domain)

    try:
        payload = json.dumps({"prefix": username, "domain": domain}).encode("utf-8")
        req = urllib.request.Request(
            f"{TMAIL_URL}/api/session/custom",
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
            data=payload,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if "address" in data:
                return data["address"]
    except Exception:
        pass

    return f"{username}@{domain}"

def solve_turnstile_capsolver(client_key: str) -> str:
    """Memanggil API CapSolver untuk menyelesaikan Cloudflare Turnstile"""
    create_url = "https://api.capsolver.com/createTask"
    task_payload = {
        "clientKey": client_key,
        "task": {
            "type": "AntiTurnstileTaskProxyLess",
            "websiteURL": SITE_URL,
            "websiteKey": SITE_KEY
        }
    }

    req = urllib.request.Request(
        create_url,
        headers={"Content-Type": "application/json"},
        data=json.dumps(task_payload).encode("utf-8"),
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode())

    if res.get("errorId", 0) != 0:
        raise Exception(f"CapSolver CreateTask Error: {res.get('errorDescription')}")

    task_id = res.get("taskId")
    print(f"[*] CapSolver Task dibuat: {task_id}. Menunggu token...")

    # Polling hasil
    result_url = "https://api.capsolver.com/getTaskResult"
    result_payload = {
        "clientKey": client_key,
        "taskId": task_id
    }

    start_time = time.time()
    while time.time() - start_time < 60:
        time.sleep(2)
        req_res = urllib.request.Request(
            result_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(result_payload).encode("utf-8"),
            method="POST"
        )
        with urllib.request.urlopen(req_res, timeout=10) as resp_res:
            res_data = json.loads(resp_res.read().decode())

        if res_data.get("status") == "ready":
            token = res_data.get("solution", {}).get("token")
            if token:
                print(f"[+] Turnstile terpecahkan! Token: {token[:16]}...")
                return token
        elif res_data.get("status") == "failed":
            raise Exception(f"CapSolver Task Gagal: {res_data.get('errorDescription')}")

    raise Exception("Timeout menunggu solusi Turnstile dari CapSolver.")

def register_account(full_name: str, username: str, email: str, password: str, turnstile_token: str) -> bool:
    reg_url = f"{API_BASE}/auth/register"
    payload = {
        "fullName": full_name,
        "username": username,
        "email": email,
        "password": password,
        "passwordConfirmation": password,
        "turnstileResponse": turnstile_token
    }

    req = urllib.request.Request(
        reg_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        data=json.dumps(payload).encode("utf-8"),
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            print(f"[+] Registrasi Berhasil: {data}")
            return True
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode()
        print(f"[-] Gagal Registrasi: {e.code} - {err_msg}")
        return False

def login_account(username: str, password: str, turnstile_token: str) -> str | None:
    login_url = f"{API_BASE}/auth/login"
    payload = {
        "email": username,
        "password": password,
        "isRememberMe": True,
        "turnstileResponse": turnstile_token
    }

    req = urllib.request.Request(
        login_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        data=json.dumps(payload).encode("utf-8"),
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            token = data.get("data", {}).get("token") or data.get("data", {}).get("value")
            return token
    except urllib.error.HTTPError as e:
        print(f"[-] Gagal Login: {e.code} - {e.read().decode()}")
        return None

def main():
    print("=" * 65)
    print("  VORATOON AUTO ACCOUNT MAKER (CAPSOLVER HEADLESS API)")
    print("=" * 65)

    client_key = os.environ.get("CAPSOLVER_API_KEY")
    if not client_key and len(sys.argv) > 1:
        client_key = sys.argv[1]

    if not client_key:
        client_key = input("\n[?] Masukkan CapSolver API Key Anda (CAP-...): ").strip()

    if not client_key:
        print("[!] CapSolver API Key diperlukan!")
        sys.exit(1)

    # Cek saldo CapSolver
    try:
        req = urllib.request.Request(
            "https://api.capsolver.com/getBalance",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"clientKey": client_key}).encode("utf-8"),
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            bal_data = json.loads(resp.read().decode())
            if bal_data.get("errorId", 0) != 0:
                print(f"[!] API Key Salah: {bal_data.get('errorDescription')}")
                sys.exit(1)
            print(f"[+] CapSolver Saldo: ${bal_data.get('balance', 0):.4f}")
    except Exception as e:
        print(f"[!] Gagal mengecek saldo CapSolver: {e}")
        sys.exit(1)

    count_str = input("[?] Berapa akun yang ingin dibuat? (Default: 9): ").strip()
    total = int(count_str) if count_str.isdigit() else 9

    used_domains = []
    created_tokens = []
    output_file = "/root/voratoon-bot/helper_accounts.txt"

    for idx in range(1, total + 1):
        full_name, username, password = generate_japanese_identity()
        email = generate_temp_email(username, used_domains)

        print(f"\n------------------------------------------------------------")
        print(f"[*] Akun #{idx}/{total}: {full_name} | {email}")
        print(f"------------------------------------------------------------")

        try:
            # 1. Solve Turnstile untuk Register
            print("[*] Meminta token Turnstile dari CapSolver untuk pendaftaran...")
            reg_turnstile = solve_turnstile_capsolver(client_key)

            # 2. Register
            success = register_account(full_name, username, email, password, reg_turnstile)
            if not success:
                print("[-] Melewati akun ini karena registrasi gagal.")
                continue

            # 3. Solve Turnstile untuk Login
            print("[*] Meminta token Turnstile dari CapSolver untuk login...")
            login_turnstile = solve_turnstile_capsolver(client_key)

            # 4. Login untuk dapatkan session token
            token = login_account(username, password, login_turnstile)
            if token:
                print(f"[SUCCESS #{idx}] Berhasil! Token: {token[:12]}...{token[-8:]}")
                created_tokens.append(token)

                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(f"Nama     : {full_name}\n")
                    f.write(f"Username : {username}\n")
                    f.write(f"Email    : {email}\n")
                    f.write(f"Password : {password}\n")
                    f.write(f"Token    : {token}\n")
                    f.write("-" * 60 + "\n")
            else:
                print("[-] Gagal mendapatkan token login.")

        except Exception as e:
            print(f"[ERROR] Kendala akun #{idx}: {e}")

    print("\n" + "=" * 65)
    print(f"[OK] Selesai! Berhasil membuat {len(created_tokens)}/{total} akun.")
    if created_tokens:
        print("\n[+] LIST TOKEN:")
        print(",".join(created_tokens))
    print("=" * 65)

if __name__ == "__main__":
    main()
