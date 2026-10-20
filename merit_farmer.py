#!/usr/bin/env python3
"""
Voratoon Daily Merit Auto-Maxer
A clean, multi-account compatible automation tool for Voratoon Cultivation system.

Features:
- Dynamic series discovery (fetches popular series automatically, no hardcoded IDs)
- Multi-account support (single token or comma-separated tokens in .env / CLI)
- Helper / Symbiotic Auto-Like Boost (+100 Merit from Resonansi Qi)
- Stealth jitter & natural human delay simulation
- Rich CLI interface (--help, --status-only, --series, --delay)
- Zero external dependencies (pure Python 3 standard library)
"""

import os
import sys
import time
import random
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

BASE_API = "https://api.voratoon.com"
ORIGIN = "https://v8.voratoon.com"
ENV_FILE = Path(__file__).parent / ".env"
CACHE_FILE = Path(__file__).parent / "claimed_chapters.json"

def load_claimed_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_claimed_cache(cache: dict):
    try:
        CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[WARN] Gagal menyimpan cache bab: {e}")

COMMENTS_POOL = [
    "Art style di chapter ini makin memanjakan mata, eksekusi visualnya gokil",
    "Alur ceritanya bener-bener gak ngebosenin, selalu seru tiap babnya",
    "Panel terakhir bener-bener bikin penasaran sama kelanjutan ceritanya",
    "Pertarungan di bagian ini seru dan intens banget, puas bacanya",
    "Karakter utamanya cerdas banget ngambil keputusan di situasi begini",
    "Pacing ceritanya rapi, perkembangan karakternya dapet banget feelnya",
    "Terjemahannya enak dibaca dan rapi, makasih banyak min udah update",
    "Plot twistnya mantap, gak nyangka bakal dibawa ke arah sini alurnya",
    "Selalu seru nungguin update tiap minggu, makin greget ceritanya",
    "Visual efek pertarungannya juara sih, berasa banget tensi adegannya",
    "Bagus banget pendalaman dunianya, salah satu komik terbaik saat ini",
    "Gak sabar nunggu kelanjutan aksinya di chapter berikutnya min",
    "Kombinasi aksi dan tensi ceritanya dapet banget di bab ini",
    "Detail gambarnya makin rapi, ekspresi karakternya hidup banget",
    "Ceritanya konsisten bagus dari awal rilis, auto masuk list favorit",
    "Koreografi pertarungannya rapi banget, enak diliat gerakannya",
    "Karakter utamanya sat-set banget gak banyak drama, suka tipe begini",
    "Semangat terus min garap komik ini, sehat selalu tim translator",
    "Komplit banget ceritanya, ada selipan santai tapi aksinya tetep dapet",
    "Kualitas gambar jernih banget, panel aksinya bener-bener memuaskan",
    "Gak pernah bosen baca komik ini, selalu ada kejutan di tiap chapter",
    "Ekspektasi terbayar lunas di bab ini, klimaks ceritanya keren banget",
    "Pengembangan karakternya terasa natural dan gak dipaksakan",
    "Tiap minggu selalu jadi komik pertama yang gw buka pas rilis",
    "Pertarungan antar karakternya berbobot, gak cuma modal teriak jurus doang"
]

SERIES_POOL = [4718, 7133, 8261, 4541, 5501, 1658, 6490, 1880, 7488, 797]

def parse_args():
    parser = argparse.ArgumentParser(
        description="Voratoon Cultivation Merit Auto-Maxer CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-t", "--token", help="Voratoon Bearer Token (overrides .env)")
    parser.add_argument("-s", "--series", default="magic-emperor", help="Target series slug for chapters")
    parser.add_argument("-d", "--delay-mult", type=float, default=1.0, help="Delay multiplier for request intervals")
    parser.add_argument("--status-only", action="store_true", help="Only check profile status and daily quotas without claiming")
    parser.add_argument("--no-boost", action="store_true", help="Disable helper account auto-like booster")
    parser.add_argument("--jitter", action="store_true", help="Aktifkan jeda acak di awal eksekusi (default: mati/instan)")
    return parser.parse_args()

def load_tokens_config(cli_token: str = None) -> tuple[list[str], str, list[str]]:
    tokens = []
    t_primary = None
    helper_tokens = []

    if cli_token:
        tokens = [t.strip() for t in cli_token.split(",") if t.strip()]
        return tokens, (tokens[0] if tokens else None), tokens[1:]

    env_token = os.environ.get("VORATOON_TOKEN")
    if env_token:
        tokens = [t.strip() for t in env_token.split(",") if t.strip()]

    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("VORATOON_TOKEN="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    tokens.extend([t.strip() for t in val.split(",") if t.strip()])
                elif line.startswith("ACCOUNT_1_TOKEN="):
                    t_primary = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("ACCOUNT_2_TOKEN="):
                    helper_tokens.append(line.split("=", 1)[1].strip().strip('"').strip("'"))

    # Load helper tokens dari HELPER_ACCOUNTS.md jika ada
    md_file = ENV_FILE.parent / "HELPER_ACCOUNTS.md"
    if md_file.exists():
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("|") and "`oat_" in line:
                        for part in line.split("|"):
                            part = part.strip()
                            if part.startswith("`oat_") and part.endswith("`"):
                                h_tok = part.strip("`")
                                if h_tok not in helper_tokens:
                                    helper_tokens.append(h_tok)
        except Exception:
            pass

    if not t_primary and tokens:
        t_primary = tokens[0]

    unique_tokens = list(dict.fromkeys(tokens))
    return unique_tokens, t_primary, helper_tokens

PROXY_OPENER = None
try:
    import socks
    from sockshandler import SocksiPyHandler
    # 1. Prioritaskan Tunnel Azure Jakarta port 1088 (Ultra-fast 15ms latency, IP fresh)
    PROXY_OPENER = urllib.request.build_opener(SocksiPyHandler(socks.SOCKS5, "127.0.0.1", 1088))
except Exception:
    PROXY_OPENER = None

TOR_OPENER = None
try:
    import socks
    from sockshandler import SocksiPyHandler
    TOR_OPENER = urllib.request.build_opener(SocksiPyHandler(socks.SOCKS5, "127.0.0.1", 9050))
except Exception:
    TOR_OPENER = None

def api_request(path: str, token: str = "", method: str = "GET", body: dict = None) -> tuple[int, dict]:
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

    # 1. Gunakan Tunnel Azure Jakarta langsung (kecepatan kilat 15ms, anti-delay, anti-429)
    if PROXY_OPENER:
        try:
            with PROXY_OPENER.open(req, timeout=10) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            if e.code != 429:
                err_body = e.read().decode("utf-8") if e.fp else ""
                try:
                    return e.code, json.loads(err_body)
                except Exception:
                    return e.code, {"error": err_body}
        except Exception:
            pass

    # 2. Fallback ke Tor SOCKS5 jika Azure tunnel bermasalah
    if TOR_OPENER:
        try:
            with TOR_OPENER.open(req, timeout=15) as resp:
                res_body = resp.read().decode("utf-8")
                return resp.status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as e:
            if e.code != 429:
                err_body = e.read().decode("utf-8") if e.fp else ""
                try:
                    return e.code, json.loads(err_body)
                except Exception:
                    return e.code, {"error": err_body}
        except Exception:
            pass

    # 3. Fallback langsung direct
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
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

def discover_series_stream(fallback_slug: str = "magic-emperor", max_pages: int = 50):
    """
    Generator cerdas yang terus menyuplai judul komik segar melintasi ribuan komik di Voratoon.
    Mencegah bot kehabisan bab komik karena komik populer sudah habis dibaca.
    """
    seen = set()

    # 1. Prioritaskan komik populer
    st_p, res_p = api_request("/popular")
    if st_p == 200 and "data" in res_p and isinstance(res_p["data"], list):
        for s in res_p["data"]:
            slug = s.get("data", {}).get("slug")
            if slug and slug not in seen:
                seen.add(slug)
                yield slug

    # 2. Jelajahi katalog lengkap /series (lebih dari 10.000 komik)
    for sort_mode in ["popularity", "bookmarks", "latest", "rating"]:
        for page in range(1, max_pages + 1):
            st, res = api_request(f"/series?page={page}&take=30&sort={sort_mode}")
            if st == 200 and "data" in res and isinstance(res["data"], list):
                items = res["data"]
                if not items:
                    break
                for s in items:
                    slug = s.get("data", {}).get("slug")
                    if slug and slug not in seen:
                        seen.add(slug)
                        yield slug
            else:
                break

    if fallback_slug not in seen:
        yield fallback_slug

def discover_series(fallback_slug: str = "magic-emperor") -> tuple[int, str]:
    st, res = api_request("/popular")
    if st == 200 and "data" in res and isinstance(res["data"], list) and len(res["data"]) > 0:
        first = res["data"][0]
        s_id = first.get("id")
        s_slug = first.get("data", {}).get("slug")
        if s_id and s_slug:
            return s_id, s_slug

    st_fb, res_fb = api_request(f"/series/{fallback_slug}")
    if st_fb == 200 and "data" in res_fb:
        return res_fb["data"].get("id", 4718), fallback_slug

    return 4718, fallback_slug

def fetch_series_chapters(series_slug: str, limit: int = 500) -> list[dict]:
    st, res = api_request(f"/series/{series_slug}/chapters")
    if st == 200 and "data" in res and isinstance(res["data"], list):
        valid = [c for c in res["data"] if isinstance(c, dict) and "id" in c]
        # Urutkan dari Chapter 1 naik ke atas (Ascending)
        valid.sort(key=lambda x: x.get("data", {}).get("index", 0))
        return valid[:limit]
    return []

def boost_helper_likes(helper_tokens: list[str], target_comment_ids: list[int]):
    if not target_comment_ids or not helper_tokens:
        return

    # Rotasi Shift A (Ganjil) & Shift B (Genap)
    import datetime
    day_num = datetime.datetime.now().timetuple().tm_yday
    shift_name = "Shift A" if day_num % 2 == 1 else "Shift B"
    
    # Prioritaskan active shift, lalu fallback ke semua helper lainnya agar PASTI mencapai 50 like!
    if len(helper_tokens) >= 20:
        active_shift = helper_tokens[:10] if shift_name == "Shift A" else helper_tokens[10:20]
        backup_shift = helper_tokens[10:20] if shift_name == "Shift A" else helper_tokens[:10]
        ordered_helpers = active_shift + backup_shift + helper_tokens[20:]
    else:
        ordered_helpers = helper_tokens

    print("\n" + "=" * 60)
    print(f"[*] Resonansi Qi: Memproses upvote ({shift_name}: target 50 Like)...")
    print("=" * 60)

    total_likes = 0
    # Voratoon limit: maksimal 50 like per hari (+100 Merit harian)
    for h_idx, h_token in enumerate(ordered_helpers, 1):
        if total_likes >= 50:
            print("[+] Target maksimal 50 Like (+100 Merit) harian telah terpenuhi!")
            break

        # 1. Suntik like ke komentar utama
        for cid in target_comment_ids:
            if total_likes >= 50:
                break
            st_u, _ = api_request(f"/comments/{cid}/upvote", token=h_token, method="POST", body={})
            if st_u in [200, 201]:
                total_likes += 1
            time.sleep(0.04)

        # 2. Klaim login + 1 bab agar akun helper naik level & natural
        try:
            api_request("/cultivation/rewards/daily-login", token=h_token, method="POST", body={})
            api_request("/cultivation/rewards/chapter", token=h_token, method="POST", body={"targetId": 235966, "mode": "chapter"})
        except Exception:
            pass

    print(f"[OK] Selesai: {total_likes}/50 like sukses disuntikkan!")

def farm_account(token: str, target_series_id: int, target_series_slug: str, delay_mult: float, status_only: bool = False) -> list[int]:
    mask_token = token[:8] + "..." + token[-6:] if len(token) > 14 else "token"
    print("\n" + "=" * 60)
    print(f"[*] Memproses Akun [{mask_token}]")
    print("=" * 60)
    created_comment_ids = []

    # 1. Profile Status
    st, me = api_request("/cultivation/me", token=token)
    if st != 200:
        print(f"[ERROR] Autentikasi Gagal ({st}): Token mungkin kedaluwarsa.")
        return

    c_data = me.get("data", {})
    daily = c_data.get("daily", {})
    print(f"[-] Pengguna   : {c_data.get('username', 'Member')}")
    print(f"[-] Kultivasi  : Level {c_data.get('level')} ({c_data.get('tier', {}).get('name', '-')})")
    print(f"[-] Total Merit: {c_data.get('merit', 0)} | Exp: {c_data.get('exp', 0)}")
    print(f"[-] Kuota Hari : Login {daily.get('login', {}).get('used', 0)}/{daily.get('login', {}).get('limit', 1)} | "
          f"Bab {daily.get('chapters', {}).get('used', 0)}/{daily.get('chapters', {}).get('limit', 50)} | "
          f"Komen {daily.get('comments', {}).get('used', 0)}/{daily.get('comments', {}).get('limit', 5)}")

    if status_only:
        print("[INFO] Mode --status-only aktif, klaim dilewati.")
        return [], None

    # 2. Daily Login Reward
    if daily.get("login", {}).get("remaining", 1) > 0:
        print("\n[1/3] Mengklaim Login Harian (+20 Merit)...")
        st_l, res_l = api_request("/cultivation/rewards/daily-login", token=token, method="POST", body={})
        if st_l in [200, 201]:
            print("  [OK] Login harian berhasil diklaim!")
        else:
            print(f"  [-] Login harian: {res_l.get('message', res_l.get('error', 'Sudah diklaim'))}")
    else:
        print("\n[1/3] Login harian sudah selesai hari ini.")

    # 3. Chapter Reads Reward (Dynamic Multi-Series Crawler with Cache)
    ch_rem = daily.get("chapters", {}).get("remaining", 50)
    if ch_rem > 0:
        print(f"\n[2/3] Membaca Chapter (Sisa kuota: {ch_rem})...")
        cache = load_claimed_cache()
        acc_key = mask_token
        claimed_set = set(cache.get(acc_key, []))

        chap_ok = 0
        series_read_counts = {}
        # Dynamic target range 52 - 60 chapter per hari
        target_reads = max(ch_rem, random.randint(52, 60))

        # Mengalirkan ribuan komik secara dinamis sampai kuota harian terpenuhi 100%
        for slug in discover_series_stream(target_series_slug, max_pages=50):
            if chap_ok >= target_reads:
                break
            chapters = fetch_series_chapters(slug, limit=500)
            if not chapters:
                continue

            for ch_item in chapters:
                cid = ch_item.get("id")
                ch_idx = ch_item.get("data", {}).get("index", "?")
                if not cid or cid in claimed_set:
                    continue

                st_c, res_c = api_request("/cultivation/rewards/chapter", token=token, method="POST", body={"targetId": cid, "mode": "chapter"})
                if st_c in [200, 201]:
                    d = res_c.get("data", {})
                    if not d.get("alreadyAwarded") and d.get("reward", {}).get("awardedMerit", 0) > 0:
                        chap_ok += 1
                    claimed_set.add(cid)
                    series_read_counts[slug] = series_read_counts.get(slug, 0) + 1

                    # Auto-Bookmark jika sudah membaca > 50 chapter di komik ini
                    if series_read_counts[slug] == 50:
                        st_b, _ = api_request(f"/series/{slug}/bookmark", token=token, method="POST", body={})
                        if st_b in [200, 201]:
                            print(f"  [+] Auto-Bookmark aktif: Komik '{slug}' ditambahkan ke Bookmark (>50 bab dibaca)!")
                else:
                    claimed_set.add(cid)

                if chap_ok >= target_reads:
                    break
                time.sleep(random.uniform(0.02, 0.05) * delay_mult)

        cache[acc_key] = list(claimed_set)
        save_claimed_cache(cache)
        print(f"  [OK] Selesai: {chap_ok} bab segar dibaca dari Ch 1 (+{min(50, chap_ok) * 10} Merit kuota penuh).")
    else:
        print("\n[2/3] Kuota baca 50 chapter sudah maksimal hari ini (50/50).")

    # 4. Comments Reward (Natural Chapter Reviews Across 5 Different Popular Comics)
    com_rem = daily.get("comments", {}).get("remaining", 5)
    if com_rem > 0:
        print(f"\n[3/3] Mengirim & Mengklaim Komentar (Sisa kuota: {com_rem})...")
        series_pool = []
        for _ in range(3):
            st_p, res_p = api_request("/popular")
            if st_p == 200 and isinstance(res_p.get("data"), list) and res_p["data"]:
                series_pool = res_p["data"]
                break
            time.sleep(1)

        if not series_pool:
            # Fallback komik populer jika /popular gagal/rate-limit
            series_pool = [
                {"id": 4718, "data": {"slug": "magic-emperor"}},
                {"id": 7133, "data": {"slug": "solo-max-level-newbie"}},
                {"id": 8261, "data": {"slug": "the-regressed-mercenarys-machinations"}},
                {"id": 4541, "data": {"slug": "leveling-in-the-future-apex-future-martial-arts"}},
                {"id": 5501, "data": {"slug": "nano-machine"}},
                {"id": 1658, "data": {"slug": "disastrous-necromancer"}},
                {"id": 6490, "data": {"slug": "revenge-of-the-iron-blooded-sword-hound"}},
                {"id": 1880, "data": {"slug": "eleceed"}},
                {"id": 7488, "data": {"slug": "swordmasters-youngest-son"}},
                {"id": 8481, "data": {"slug": "the-ultimate-of-all-ages"}}
            ]
        
        # Pick distinct series so we NEVER spam 1 comic
        chosen_series = random.sample(series_pool, min(com_rem, len(series_pool))) if series_pool else []
        selected_comments = random.sample(COMMENTS_POOL, min(com_rem, len(COMMENTS_POOL)))
        comm_ok = 0

        for idx in range(len(chosen_series)):
            item = chosen_series[idx]
            s_id = item.get("id")
            s_slug = item.get("data", {}).get("slug", target_series_slug)
            
            # Fetch recent chapters: wajib komentar di dalam chapter spesifik!
            chaps = fetch_series_chapters(s_slug, limit=20)
            if not chaps:
                continue
            # Pick a chapter randomly among available chapters
            ch_choice = random.choice(chaps[:min(10, len(chaps))])
            c_id = ch_choice.get("id") if isinstance(ch_choice, dict) else ch_choice
            
            text = selected_comments[idx]
            body = {
                "seriesId": s_id,
                "chapterId": c_id,
                "content": text
            }

            st_post, res_post = api_request("/comments", token=token, method="POST", body=body)
            if st_post in [200, 201] and "data" in res_post and "id" in res_post["data"]:
                cid = res_post["data"]["id"]
                created_comment_ids.append(cid)
                st_claim, _ = api_request("/cultivation/rewards/comment", token=token, method="POST", body={"targetId": cid})
                if st_claim in [200, 201]:
                    comm_ok += 1
                    print(f"  [OK] Komentar #{comm_ok} di {s_slug} [Chapter {c_id}]: \"{text[:45]}...\"")
            time.sleep(random.uniform(0.1, 0.25) * delay_mult)

        print(f"  [OK] Selesai: {comm_ok}/{len(chosen_series)} komentar bab berhasil diklaim (+{comm_ok * 15} Merit).")
    else:
        print("\n[3/3] Kuota 5 komentar sudah maksimal hari ini (5/5).")

    # 5. Final Status
    result_data = None
    st_f, final_me = api_request("/cultivation/me", token=token)
    if st_f == 200:
        fd = final_me.get("data", {})
        f_daily = fd.get("daily", {})
        gained = fd.get("merit", 0) - c_data.get("merit", 0)
        print("\n" + "-" * 60)
        print(f"[STATUS] Level {fd.get('level')} | Total Merit {fd.get('merit')} (+{gained})")
        print(f"[STATUS] Hasil Hari Ini: Login {f_daily.get('login', {}).get('used')}/{f_daily.get('login', {}).get('limit')} | "
              f"Bab {f_daily.get('chapters', {}).get('used')}/{f_daily.get('chapters', {}).get('limit')} | "
              f"Komen {f_daily.get('comments', {}).get('used')}/{f_daily.get('comments', {}).get('limit')}")
        result_data = {
            "level": fd.get("level"),
            "merit": fd.get("merit"),
            "gained": gained,
            "tier": fd.get("tier", {}).get("name", "Commoner"),
            "daily": f_daily,
            "username": fd.get("username", "Member")
        }

    return created_comment_ids, result_data

def send_telegram_alert(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    try:
        hermes_env = Path("/root/.hermes/.env")
        if not token and hermes_env.exists():
            with open(hermes_env, "r") as f:
                for line in f:
                    if line.startswith("TELEGRAM_BOT_TOKEN="):
                        token = line.strip().split("=", 1)[1].strip('"\'')
    except Exception:
        pass
    if not token:
        return

    targets = [
        {"chat_id": "5678748710"},
        {"chat_id": "-1004385053126", "thread_id": 572}
    ]
    for tgt in targets:
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": tgt["chat_id"],
                "text": text,
                "parse_mode": "Markdown"
            }
            if "thread_id" in tgt:
                payload["message_thread_id"] = int(tgt["thread_id"])
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10):
                pass
        except Exception:
            pass

def main():
    args = parse_args()
    tokens, primary_token, helper_tokens = load_tokens_config(args.token)

    if not tokens:
        print("[ERROR] Tidak ada token Voratoon yang ditemukan!")
        sys.exit(1)

    # Jitter delay opsional (hanya jika flag --jitter diaktifkan)
    if args.jitter and not args.status_only:
        jitter_s = random.randint(30, 180)
        print(f"[*] Jitter Delay: Menunggu jeda acak {jitter_s} detik...")
        time.sleep(jitter_s)

    print("=" * 60)
    print("Voratoon Cultivation Merit Auto-Maxer")
    print("=" * 60)
    print(f"[*] Ditemukan {len(tokens)} akun utama dan {len(helper_tokens)} akun helper.")

    target_id, target_slug = discover_series(args.series)
    print(f"[*] Target Series Default: {target_slug} (ID: {target_id})")

    primary_created_comments = []
    results = []

    # 1. PRIORITAS #1: Eksekusi Akun Utama Kilat (<4 detik) untuk langsung mengunci 695 Merit & RANK #1
    if primary_token:
        print("[*] MEMPROSES AKUN UTAMA (PRIORITAS TINGGI)...")
        try:
            cids, res = farm_account(primary_token, target_id, target_slug, args.delay_mult, status_only=args.status_only)
            if cids:
                primary_created_comments = cids
            if res:
                results.append((1, res))

            # Jika cids kosong (misal komentar sudah dibuat sebelumnya), ambil 5 komentar terbaru dari profil
            if not primary_created_comments:
                st_uc, res_uc = api_request("/user/comments", token=primary_token)
                if st_uc == 200 and isinstance(res_uc.get("data"), list):
                    primary_created_comments = [c["id"] for c in res_uc["data"][:5] if "id" in c]

            # LANGSUNG SUNTIK 50 LIKES KE AKUN UTAMA DETIK INI JUGA (TANPA MENUNGGU AKUN LAIN!)
            if not args.status_only and not args.no_boost and helper_tokens and primary_created_comments:
                print("\n[*] LANGSUNG MENYUNTIK 50 LIKE HELPER KE AKUN UTAMA...")
                boost_helper_likes(helper_tokens, primary_created_comments)

                # Konfirmasi Peringkat Akun Utama Langsung di Detik Awal
                try:
                    st_lb, res_lb = api_request("/rankings/users", token=primary_token)
                    if st_lb == 200:
                        my = res_lb.get("myRank", {})
                        print(f"\n[👑 TAHTA] AKUN UTAMA SUKSES MAKSIMAL! Peringkat: Rank #{my.get('rank')} ({my.get('periodMerit'):,} Weekly Merit)!")
                except Exception:
                    pass
        except Exception as e:
            print(f"[ERROR] Masalah pada akun utama: {e}")

    # 2. PROSES AKUN-AKUN HELPER BERIKUTNYA
    other_tokens = tokens[1:]
    for idx, token in enumerate(other_tokens, 2):
        try:
            cids, res = farm_account(token, target_id, target_slug, args.delay_mult, status_only=args.status_only)
            if res:
                results.append((idx, res))
        except Exception as e:
            print(f"[ERROR] Masalah pada akun #{idx}: {e}")

    print("\n" + "=" * 60)
    print("[OK] Seluruh antrean akun dan auto-boost selesai diproses.")
    print("=" * 60)

    # 3. Kirim notifikasi Telegram otomatis dengan status Leaderboard Nasional
    if not args.status_only and results:
        lines = ["*Laporan Harian Voratoon Merit Auto-Maxer*", ""]
        for idx, r in results:
            role = "Akun Utama" if idx == 1 else f"Akun Helper #{idx - 1}"
            d = r.get("daily", {})
            lines.append(f"*{role}:*")
            lines.append(f"- Level: {r.get('level')} ({r.get('tier')})")
            lines.append(f"- Total Merit: {r.get('merit'):,} (+{r.get('gained')})")
            lines.append(f"- Kuota: Login {d.get('login', {}).get('used')}/{d.get('login', {}).get('limit')} | Bab {d.get('chapters', {}).get('used')}/{d.get('chapters', {}).get('limit')} | Komen {d.get('comments', {}).get('used')}/{d.get('comments', {}).get('limit')}")
            lines.append("")

        # Live Leaderboard Checking
        try:
            st_lb, res_lb = api_request("/rankings/users", token=primary_token)
            if st_lb == 200:
                my = res_lb.get("myRank", {})
                r_pos = my.get("rank", "-")
                w_merit = my.get("periodMerit", 0)
                top1_merit = res_lb.get("data", [{}])[0].get("merit", 0)
                diff = max(0, top1_merit - w_merit)
                lines.append(f"*Status Leaderboard Mingguan:*")
                lines.append(f"- Peringkat: *Rank #{r_pos}*")
                lines.append(f"- Merit Mingguan: {w_merit:,}")
                lines.append(f"- Selisih ke Top 1: {diff:,} Merit")
                lines.append("")
        except Exception:
            pass

        lines.append("Status: Otomatisasi berjalan lancar pada crontab VPS.")
        send_telegram_alert("\n".join(lines))

if __name__ == "__main__":
    main()
