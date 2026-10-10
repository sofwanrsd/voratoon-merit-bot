#!/usr/bin/env python3
"""
Voratoon Daily Merit Auto-Maxer (Full Complete Automation)
Farms 100% maximum daily limits:
- Daily Login (+20) [1/1]
- 50 Chapter Reads (+500) [50/50]
- 5 Comments (+75) [5/5]
- Status Verification
"""

import os
import sys
import time
import random
import json
import urllib.request
import urllib.error
from pathlib import Path

BASE_API = "https://api.voratoon.com"
ORIGIN = "https://v8.voratoon.com"

ENV_FILE = Path(__file__).parent / ".env"

def get_token() -> str:
    if len(sys.argv) > 1 and sys.argv[1].startswith("oat_"):
        return sys.argv[1].strip()
    
    token = os.environ.get("VORATOON_TOKEN")
    if token:
        return token.strip()
    
    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("VORATOON_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    
    return ""

def api_request(path: str, token: str, method: str = "GET", body: dict = None) -> tuple[int, dict]:
    url = f"{BASE_API}{path}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": ORIGIN,
        "Referer": f"{ORIGIN}/",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res_body = resp.read().decode("utf-8")
            return resp.status, json.loads(res_body) if res_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        try:
            return e.code, json.loads(err_body)
        except Exception:
            return e.code, {"error": err_body}
    except Exception as e:
        return 500, {"error": str(e)}

def fetch_target_chapters() -> list[int]:
    status, res = api_request("/series/magic-emperor/chapters", token="")
    if status == 200 and "data" in res:
        chapters = [c["id"] for c in res["data"] if isinstance(c, dict) and "id" in c]
        return chapters[:50]
    return []

def run_farm():
    token = get_token()
    if not token:
        print("[ERROR] Token Voratoon belum disetel!")
        sys.exit(1)
    
    print("=" * 55)
    print("🚀 VORATOON DAILY MERIT AUTO-MAXER RUNNING")
    print("=" * 55)
    
    # Check Profile
    status, me = api_request("/cultivation/me", token=token)
    if status != 200:
        print(f"[ERROR] Failed to authenticate ({status}). Response: {me}")
        sys.exit(1)
    
    cur_data = me.get("data", {})
    print(f"Level: {cur_data.get('level')} | Merit: {cur_data.get('merit')} | Exp: {cur_data.get('exp')}")

    # 1. Daily Login
    st, res = api_request("/cultivation/rewards/daily-login", token=token, method="POST", body={})
    print(f"✓ Daily Login: {'OK (+20)' if st in [200, 201] else 'Already claimed'}")

    # 2. 50 Chapters
    chapters = fetch_target_chapters()
    if chapters:
        print(f"→ Processing {len(chapters)} chapter reads with stealth jitter...")
        chap_ok = 0
        for cid in chapters:
            st, _ = api_request("/cultivation/rewards/chapter", token=token, method="POST", body={"targetId": cid, "mode": "chapter"})
            if st in [200, 201]:
                chap_ok += 1
            # Random delay jitter between 0.25s and 0.65s (looks like human scrolling)
            time.sleep(random.uniform(0.25, 0.65))
        print(f"✓ Chapters: {chap_ok}/{len(chapters)} claims recorded")

    # 3. 5 Comments (> 5 words each, randomized pool)
    comments_pool = [
        "Karakter utamanya semakin berkembang sangat baik di sini",
        "Alur ceritanya tidak membosankan dan selalu seru dibaca",
        "Kualitas art dan visual komik ini sangat memanjakan mata",
        "Pertarungan di bagian ini sangat menegangkan dan memuaskan",
        "Terima kasih untuk mimin yang selalu update dengan cepat",
        "Plot twist di chapter ini bener-bener gak ketebak sama sekali",
        "Gak sabar nunggu kelanjutan cerita di chapter berikutnya",
        "Panel terakhir bener-bener bikin penasaran kelanjutannya",
        "Visualisasi jurus dan efek pertarungannya keren banget",
        "Pembangunan karakter sampingannya juga dapet banget feelnya",
        "Semoga mimin sehat selalu dan lancar terus garapannya",
        "Bagus banget ceritanya, sangat rekomendasi buat dibaca maraton",
        "Art style makin ke sini makin rapi dan detail banget",
        "Konflik ceritanya makin matang dan seru buat diikutin",
        "Gokil sih ini adaptasinya rapi banget terjemahannya"
    ]
    selected_comments = random.sample(comments_pool, 5)
    print("→ Processing 5 organic comment rewards...")
    comm_ok = 0
    for text in selected_comments:
        st_c, res_c = api_request("/comments", token=token, method="POST", body={"seriesId": 4718, "content": text})
        if st_c in [200, 201] and "data" in res_c and "id" in res_c["data"]:
            cid = res_c["data"]["id"]
            st_cl, _ = api_request("/cultivation/rewards/comment", token=token, method="POST", body={"targetId": cid})
            if st_cl in [200, 201]:
                comm_ok += 1
        time.sleep(random.uniform(0.8, 1.6))
    print(f"✓ Comments: {comm_ok}/5 rewards recorded")

    # Final Verification
    _, final_me = api_request("/cultivation/me", token=token)
    fd = final_me.get("data", {})
    daily = fd.get("daily", {})
    print("-" * 55)
    print(f"★ FINAL STATUS: Level {fd.get('level')} | Total Merit {fd.get('merit')}")
    print(f"★ DAILY STATS : Login {daily.get('login', {}).get('used')}/{daily.get('login', {}).get('limit')} | Chapters {daily.get('chapters', {}).get('used')}/{daily.get('chapters', {}).get('limit')} | Comments {daily.get('comments', {}).get('used')}/{daily.get('comments', {}).get('limit')}")
    print("=" * 55)

if __name__ == "__main__":
    run_farm()
