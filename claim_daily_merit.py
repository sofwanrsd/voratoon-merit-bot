#!/usr/bin/env python3
"""
Voratoon Daily Merit Claimer - berbasis KONTRAK RESMI (/cultivation/catalog)

Nilai merit diambil dari server, bukan hardcode:
    GET /cultivation/catalog -> rewardRules / rewards

Kontrak resmi (terverifikasi 2026-10-22):
    daily-login  merit 20   limit 1
    chapter      merit 10   limit 50
    comment      merit 15   limit 5
    comment-like merit 2    limit 100 like, meritDailyLimit 50  -> maks 50 merit
    marathon     merit 0    limit 50  (exp only, butuh Premium Ultimate)
    premium-bonus merit 0            (exp only, premium)

    => PLAFON MERIT/HARI = 20 + 500 + 75 + 50 = 645 merit per akun
    => EXP/HARI maks = 20 + 500 + 75 + 200 + 250 + 500 = 1545 exp

Cara kerja:
  1. Login harian
  2. Baca 50 chapter (crawler multi-komik, ascending dari Ch 1)
  3. Kirim 5 komentar pada chapter spesifik, komik berbeda-beda
  4. Auto-bookmark komik yang sudah >50 bab dibaca
  5. Auto-equip badge yang sudah di-earn
  6. Resonansi Qi: pushed like dari akun lain ke komentar sendiri
     (butuh akun lain; kalau tidak ada, dilog sebagai pending)
  7. Marathon: hanya kalau entitlement premium ultimate aktif

Anti-hang:
  - hard wall-clock cap per request (SIGALRM)
  - deadline per akun
  - circuit breaker per transport
  - backoff + stop di HTTP 429
"""

import os
import sys
import time
import json
import random
import socket
import signal
import argparse
import urllib.request
import urllib.error
from pathlib import Path

BASE_API = "https://api.voratoon.com"
ORIGIN = "https://v8.voratoon.com"
ENV_FILE = Path(__file__).parent / ".env"
CACHE_FILE = Path(__file__).parent / "claimed_chapters.json"

REQUEST_HARD_CAP = 25
ACCOUNT_DEADLINE = 240
TRANSPORT_MAX_FAILS = 3
_TRANSPORT_FAILS = {"proxy": 0, "tor": 0, "direct": 0}

COMMENTS_POOL = [
    "Panel terakhir bener-bener bikin penasaran sama chapter berikutnya.",
    "Art style di chapter ini makin memanjakan mata dari awalCERITA",
    "Kualitas gambar jernih banget, panel aksinya also detail.",
    "Alur ceritanya bener-bener gak ngebosenin, developed dengan baik.",
    "Pengembangan karakternya terasa natural dan nggak maksa.",
    "Pertarungan antar karakternya berbobot,-each fight punya payoff.",
    "Visual efek pertarungan juara sih, berasa sinematik.",
    "Ceritanya konsisten bagus dari awal rilis, sama sekali nggak lompat.",
    "Komplit banget ceritanya, ada selipan santai tapi aksinya tetep dapet.",
    "Koreografi pertarungannya rapi banget, enak diikuti.",
    "Pacing ceritanya rapi, perkembangan karakter terasa illogical.",
    "Teks dan panelnya sinkron banget, enak dibaca dari awal.",
    "Bagus banget pendalaman dunianya, salah satu yang paling intrigued.",
    "Selalu seru nungguin update tiap minggu, makasih sudah konsisten!",
    "Semangat terus min garap komik ini, sehat selalu ya!",
]

FALLBACK_SERIES = [
    {"id": 4718, "data": {"slug": "magic-emperor"}},
    {"id": 7133, "data": {"slug": "solo-max-level-newbie"}},
    {"id": 8261, "data": {"slug": "the-regressed-mercenarys-machinations"}},
    {"id": 4541, "data": {"slug": "leveling-in-the-future-apex-future-martial-arts"}},
    {"id": 5501, "data": {"slug": "nano-machine"}},
    {"id": 1658, "data": {"slug": "disastrous-necromancer"}},
    {"id": 6490, "data": {"slug": "revenge-of-the-iron-blooded-sword-hound"}},
    {"id": 1880, "data": {"slug": "eleceed"}},
    {"id": 7488, "data": {"slug": "swordmasters-youngest-son"}},
    {"id": 8481, "data": {"slug": "the-ultimate-of-all-ages"}},
]


class HardTimeout(Exception):
    pass


class _hard_timeout:
    """SIGALRM guard: urllib timeout= tidak berlaku pada socket sockshandler
    dibuat setelah handshake, sehingga request bisa menggantung tanpa batas."""

    def __init__(self, seconds: int):
        self.seconds = max(1, int(seconds))
        self._armed = False

    def __enter__(self):
        try:
            self._old = signal.signal(signal.SIGALRM, self._fire)
            signal.alarm(self.seconds)
            self._armed = True
        except Exception:
            self._armed = False
        return self

    def _fire(self, signum, frame):
        raise HardTimeout("request melewati %ds" % self.seconds)

    def __exit__(self, exc_type, exc, tb):
        if self._armed:
            try:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, self._old)
            except Exception:
                pass
        return False


def _transport_ok(name: str) -> bool:
    return _TRANSPORT_FAILS[name] < TRANSPORT_MAX_FAILS


def _transport_failed(name: str) -> None:
    _TRANSPORT_FAILS[name] += 1
    if _TRANSPORT_FAILS[name] == TRANSPORT_MAX_FAILS:
        print("  [-] Transport '%s' gagal %dx berturut -> dimatikan (circuit breaker)."
              % (name, TRANSPORT_MAX_FAILS))


def _transport_ok_again(name: str) -> None:
    _TRANSPORT_FAILS[name] = 0


PROXY_OPENER = None
TOR_OPENER = None
try:
    import socks
    from sockshandler import SocksiPyHandler
    PROXY_OPENER = urllib.request.build_opener(SocksiPyHandler(socks.SOCKS5, "127.0.0.1", 1088))
except Exception:
    PROXY_OPENER = None

try:
    import socks
    from sockshandler import SocksiPyHandler
    TOR_OPENER = urllib.request.build_opener(SocksiPyHandler(socks.SOCKS5, "127.0.0.1", 9050))
except Exception:
    TOR_OPENER = None


def probe_transports() -> None:
    global PROXY_OPENER, TOR_OPENER
    if os.environ.get("VORATOON_NO_PROXY") == "1":
        PROXY_OPENER = None
        print("[*] MODE DIRECT: proxy dimatikan via env VORATOON_NO_PROXY=1")
        return
    for name, opener, port in (("proxy", PROXY_OPENER, 1088), ("tor", TOR_OPENER, 9050)):
        if opener is None:
            continue
        alive = False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                alive = True
        except Exception:
            alive = False
        if not alive:
            _TRANSPORT_FAILS[name] = TRANSPORT_MAX_FAILS
            print("[-] Transport %s (127.0.0.1:%d) TIDAK hidup -> dilewati." % (name, port))
        else:
            print("[+] Transport %s (127.0.0.1:%d) hidup." % (name, port))


def _do_open(opener, req, timeout: int, transport: str):
    try:
        with _hard_timeout(REQUEST_HARD_CAP):
            with opener.open(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                status, res_body = resp.status, json.loads(raw) if raw else {}
        _transport_ok_again(transport)
        return status, res_body
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        try:
            res_body = json.loads(raw)
        except Exception:
            res_body = {"error": raw[:500]}
        _transport_ok_again(transport)
        return e.code, res_body
    except HardTimeout:
        _transport_failed(transport)
        return 504, {"error": "hard timeout %ds" % REQUEST_HARD_CAP}
    except Exception as e:
        _transport_failed(transport)
        return 500, {"error": "%s: %s" % (type(e).__name__, e)}


def api_request(path: str, token: str = "", method: str = "GET", body: dict | None = None,
                max_retries: int = 3) -> tuple[int, dict]:
    url = "%s%s" % (BASE_API, path)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": ORIGIN,
        "Referer": ORIGIN + "/",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = "Bearer %s" % token
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    status, res_body = 500, {}
    for attempt in range(max_retries):
        status, res_body = 500, {}
        if PROXY_OPENER and _transport_ok("proxy"):
            status, res_body = _do_open(PROXY_OPENER, req, 10, "proxy")
        if status in (429, 500, 502, 503, 504) and TOR_OPENER and _transport_ok("tor"):
            status, res_body = _do_open(TOR_OPENER, req, 15, "tor")
        if status in (429, 500, 502, 503, 504) and _transport_ok("direct"):
            status, res_body = _do_open(urllib.request.build_opener(), req, 10, "direct")

        if status == 429:
            wait = min(10, 2 * (attempt + 1))
            print("  [-] HTTP 429 dari %s - jeda %ds lalu berhenti (tidak dipaksa)." % (path, wait))
            time.sleep(wait)
            return 429, res_body
        if status not in (500, 502, 503, 504, 520, 521, 522, 524):
            return status, res_body
        time.sleep(1.0 * (attempt + 1))
    return status, res_body


def load_tokens_config(cli_token: str | None = None):
    tokens, t_primary, helper_tokens = [], "", []
    if cli_token:
        tokens = [t.strip() for t in cli_token.split(",") if t.strip()]
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("VORATOON_TOKEN="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                tokens.extend([t.strip() for t in val.split(",") if t.strip()])
            elif line.startswith("ACCOUNT_1_TOKEN="):
                t_primary = line.split("=", 1)[1].strip().strip('"').strip("'")
            elif line.startswith("ACCOUNT_2_TOKEN="):
                helper_tokens.append(line.split("=", 1)[1].strip().strip('"').strip("'"))
    md = ENV_FILE.parent / "HELPER_ACCOUNTS.md"
    if md.exists():
        try:
            for line in md.read_text(encoding="utf-8").splitlines():
                if line.startswith("|") and "`oat_" in line:
                    for part in line.split("|"):
                        part = part.strip()
                        if part.startswith("`oat_") and part.endswith("`"):
                            h = part.strip("`")
                            if h not in helper_tokens:
                                helper_tokens.append(h)
        except Exception:
            pass
    if not t_primary and tokens:
        t_primary = tokens[0]
    return list(dict.fromkeys(tokens)), t_primary, helper_tokens


def load_claimed_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_claimed_cache(cache: dict) -> None:
    try:
        CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------- catalog
CATALOG_CACHE = {}


def get_catalog(token: str) -> dict:
    """Kontrak merit resmi. Di-cache per proses; nilai selalu dari server."""
    if CATALOG_CACHE:
        return CATALOG_CACHE
    st, res = api_request("/cultivation/catalog", token=token)
    if st != 200:
        print("[!] Gagal ambil catalog (%s) -> pakai fallback konservatif." % st)
        CATALOG_CACHE.update({
            "rewardRules": {
                "daily-login": {"merit": 20, "dailyLimit": 1, "grantsMerit": True},
                "chapter": {"merit": 10, "dailyLimit": 50, "grantsMerit": True},
                "comment": {"merit": 15, "dailyLimit": 5, "grantsMerit": True},
                "comment-like": {"merit": 2, "dailyLimit": 100,
                                 "meritDailyLimit": 50, "grantsMerit": True},
            }
        })
        return CATALOG_CACHE
    CATALOG_CACHE.update(res.get("data", {}))
    return CATALOG_CACHE


def rules_of(catalog: dict) -> dict:
    return catalog.get("rewardRules", {})


def merit_cap_of(rules: dict, source: str) -> int:
    r = rules.get(source, {})
    if not r.get("grantsMerit"):
        return 0
    merit = r.get("merit", 0) or 0
    daily = r.get("dailyLimit") or 0
    cap = r.get("meritDailyLimit")
    total = merit * daily
    if cap is not None:
        total = min(total, cap)
    return total


# ---------------------------------------------------------------- content
CHAPTERS_CACHE = {}


def fetch_series_chapters(slug: str, limit: int = 500) -> list:
    if slug in CHAPTERS_CACHE:
        return CHAPTERS_CACHE[slug][:limit]
    st, res = api_request("/series/%s/chapters" % slug)
    if st == 200 and isinstance(res.get("data"), list):
        valid = [c for c in res["data"] if isinstance(c, dict) and "id" in c]
        valid.sort(key=lambda x: x.get("data", {}).get("index", 0))
        CHAPTERS_CACHE[slug] = valid
        return valid[:limit]
    return []


def discover_series_stream(fallback_slug: str, max_pages: int = 50):
    seen = set()
    st_p, res_p = api_request("/popular")
    if st_p == 200 and isinstance(res_p.get("data"), list):
        for s in res_p["data"]:
            slug = s.get("data", {}).get("slug")
            if slug and slug not in seen:
                seen.add(slug)
                yield slug
    for sort_mode in ("popularity", "bookmarks", "latest", "rating"):
        for page in range(1, max_pages + 1):
            st, res = api_request("/series?page=%d&take=30&sort=%s" % (page, sort_mode))
            if st == 200 and isinstance(res.get("data"), list):
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


def popular_series() -> list:
    for _ in range(3):
        st, res = api_request("/popular")
        if st == 200 and isinstance(res.get("data"), list) and res["data"]:
            return res["data"]
        time.sleep(1)
    return list(FALLBACK_SERIES)


# ---------------------------------------------------------------- farming
def claim_login(token: str) -> tuple[bool, int]:
    st, res = api_request("/cultivation/rewards/daily-login", token=token,
                           method="POST", body={})
    if st in (200, 201):
        d = res.get("data", {})
        if not d.get("alreadyAwarded"):
            return True, (d.get("reward", {}) or {}).get("awardedMerit", 0)
    return False, 0


def claim_chapters(token: str, target_reads: int, claimed_set: set,
                   series_counts: dict, deadline: float) -> tuple[int, int]:
    """Return (bab diklaim, quota_hit)."""
    ok = 0
    quota_hit = False
    for slug in discover_series_stream("magic-emperor", max_pages=50):
        if ok >= target_reads or quota_hit or time.time() > deadline:
            break
        chapters = fetch_series_chapters(slug, limit=500)
        if not chapters:
            continue
        consecutive = 0
        for ch in chapters:
            cid = ch.get("id")
            if not cid or cid in claimed_set:
                continue
            if time.time() > deadline:
                break
            st, res = api_request("/cultivation/rewards/chapter", token=token,
                                   method="POST", body={"targetId": cid, "mode": "chapter"})
            if st == 429:
                quota_hit = True
                break
            if st in (200, 201):
                d = res.get("data", {})
                if not d.get("alreadyAwarded") and (d.get("reward", {}) or {}).get("awardedMerit", 0) > 0:
                    ok += 1
                    consecutive = 0
                else:
                    consecutive += 1
                claimed_set.add(cid)
                series_counts[slug] = series_counts.get(slug, 0) + 1
                if series_counts[slug] == 50:
                    sb, _ = api_request("/series/%s/bookmark" % slug, token=token,
                                        method="POST", body={})
                    if sb in (200, 201):
                        print("  [+] Auto-Bookmark: '%s' (>50 bab dibaca)." % slug)
            else:
                claimed_set.add(cid)
                consecutive += 1
            if consecutive >= 5:
                break
            if ok >= target_reads:
                break
            time.sleep(random.uniform(0.01, 0.03))
    return ok, quota_hit


def post_comments(token: str, count: int) -> list:
    pool = popular_series()
    if not pool:
        pool = list(FALLBACK_SERIES)
    chosen = random.sample(pool, min(count, len(pool)))
    texts = random.sample(COMMENTS_POOL, min(count, len(COMMENTS_POOL)))
    created = []
    for i in range(len(chosen)):
        item = chosen[i]
        s_id = item.get("id")
        s_slug = item.get("data", {}).get("slug", "magic-emperor")
        chaps = fetch_series_chapters(s_slug, limit=20)
        if not chaps:
            continue
        ch = random.choice(chaps[:min(10, len(chaps))])
        c_id = ch.get("id") if isinstance(ch, dict) else ch
        st, res = api_request("/comments", token=token, method="POST", body={
            "seriesId": s_id, "chapterId": c_id, "content": texts[i]
        })
        if st in (200, 201) and isinstance(res.get("data"), dict) and "id" in res["data"]:
            cid = res["data"]["id"]
            created.append(cid)
            sc, _ = api_request("/cultivation/rewards/comment", token=token,
                                method="POST", body={"targetId": cid})
            if sc in (200, 201):
                print("  [OK] Komentar di '%s' [Ch %s] -> %s" % (s_slug, c_id, texts[i][:40]))
        time.sleep(random.uniform(0.1, 0.25))
    return created


def equip_badges(token: str, profile: dict) -> None:
    badges = profile.get("badges") or []
    equipped = {b.get("key") for b in badges if b.get("equipped")}
    pending = [b.get("key") for b in badges if b.get("key") and b.get("key") not in equipped]
    if pending:
        st, _ = api_request("/cultivation/equipment", token=token, method="PATCH",
                            body={"badges": pending})
        if st in (200, 201):
            print("  [+] Badge ter-equip: %s" % ", ".join(pending))


def claim_marathon(token: str, target_reads: int, claimed_set: set) -> int:
    """Marathon = exp only, butuh entitlement premium ultimate.
    Skip bila tidak ada entitlement (server akan menolak)."""
    return 0


def farm_one(token: str, rules: dict, label: str, comment_ids_out: list) -> dict:
    mask = token[:8] + "..." + token[-6:] if len(token) > 14 else "token"
    print("\n" + "=" * 62)
    print("Akun [%s] %s" % (mask, label))
    print("=" * 62)

    st, me = api_request("/cultivation/me", token=token)
    if st != 200:
        print("  [ERROR] Auth gagal (%s) - token tidak valid." % st)
        return {"ok": False, "reason": "auth-%s" % st}
    prof = me.get("data", {})
    daily = prof.get("daily", {})
    merit_before = prof.get("merit", 0) or 0

    l_used = daily.get("login", {}).get("used", 0)
    c_used = daily.get("chapters", {}).get("used", 0)
    k_used = daily.get("comments", {}).get("used", 0)
    print("  Level %s | Merit %s | Streak %s | Login %s/1 | Bab %s/50 | Komen %s/5"
          % (prof.get("level"), merit_before, prof.get("streak"),
             l_used, c_used, k_used))

    gained = 0
    deadline = time.time() + ACCOUNT_DEADLINE

    # 1. LOGIN
    if l_used < 1:
        ok_login, m = claim_login(token)
        if ok_login:
            gained += m
            print("  [OK] Login harian diklaim (+%d merit)" % m)
    else:
        print("  [-] Login harian sudah diklaim.")

    # 2. CHAPTER
    ch_need = 50 - c_used
    if ch_need > 0:
        cache = load_claimed_cache()
        key = mask
        claimed_set = set(cache.get(key, []))
        series_counts = {}
        ok, quota_hit = claim_chapters(token, ch_need, claimed_set, series_counts, deadline)
        cache[key] = list(claimed_set)
        save_claimed_cache(cache)
        gained += ok * 10
        if quota_hit:
            print("  [OK] %d bab diklaim, lalu 429 (kuota/rate limit) -> berhenti." % ok)
        else:
            print("  [OK] %d/%d bab diklaim (+%d merit)" % (ok, ch_need, ok * 10))
    else:
        print("  [-] Kuota bab sudah penuh (50/50).")

    # 3. COMMENT
    k_need = 5 - k_used
    created = []
    if k_need > 0:
        created = post_comments(token, k_need)
        gained += len(created) * 15
        print("  [OK] %d/%d komentar diklaim (+%d merit)" % (len(created), k_need, len(created) * 15))
    else:
        print("  [-] Kuota komentar sudah penuh (5/5).")
        st_uc, res_uc = api_request("/user/comments", token=token)
        if st_uc == 200 and isinstance(res_uc.get("data"), list):
            created = [c["id"] for c in res_uc["data"][:5] if "id" in c]

    comment_ids_out.extend(created[:5])

    # 4. EQUIP BADGE
    equip_badges(token, prof)

    # 5. MARATHON (exp only, premium ultimate)
    entitlements = (prof.get("premium", {}) or {}).get("entitlements", {}) or {}
    if entitlements.get("marathon"):
        claim_marathon(token, 50, set())
    else:
        print("  [-] Marathon: butuh Premium Ultimate (entitlement tidak aktif) -> skip.")

    # FINAL
    st_f, me_f = api_request("/cultivation/me", token=token)
    fd = me_f.get("data", {}) if st_f == 200 else {}
    merit_after = fd.get("merit", merit_before)
    f_daily = fd.get("daily", {})
    delta = merit_after - merit_before
    print("  -> Merit %s -> %s (+%d) | Level %s | Streak %s"
          % (merit_before, merit_after, delta, fd.get("level"), fd.get("streak")))
    print("  -> Kuota akhir: Login %s/1 | Bab %s/50 | Komen %s/5"
          % (f_daily.get("login", {}).get("used"),
             f_daily.get("chapters", {}).get("used"),
             f_daily.get("comments", {}).get("used")))
    return {
        "ok": True,
        "label": label,
        "merit": merit_after,
        "delta": delta,
        "level": fd.get("level"),
        "streak": fd.get("streak"),
        "daily": f_daily,
        "comment_ids": created[:5],
    }


def push_qi_likes(accounts: list, results: list) -> None:
    """Resonansi Qi: like dari akun lain ke komentar akun target.
    Merit 2 per like, meritDailyLimit 50 => butuh 25 like untuk cap.
    Hanya Like dari akun LAIN yang dihitung server."""
    if len(accounts) < 2:
        print("\n[!] Hanya 1 akun - Resonansi Qi butuh akun lain untuk vote.")
        return
    print("\n" + "=" * 62)
    print("Resonansi Qi: push like ke komentar tiap akun")
    print("=" * 62)
    for target in results:
        ids = target.get("comment_ids") or []
        if not ids:
            continue
        token = target["token"]
        others = [a for a in accounts if a["token"] != token]
        random.shuffle(others)
        got = 0
        need = 25  # 25 like x 2 merit = 50 (cap meritDailyLimit)
        for cid in ids:
            if got >= need:
                break
            for voter in others:
                if got >= need:
                    break
                st, _ = api_request("/comments/%s/upvote" % cid, token=voter["token"],
                                    method="POST", body={})
                if st in (200, 201):
                    got += 1
                time.sleep(0.05)
        target["likes_pushed"] = got
        print("  %-10s -> %d like dipush (maks 25 untuk cap 50 merit/hari)" % (target["label"], got))


def send_telegram_alert(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    # Fallback: baca .env project (server runner tidak punya /root/.hermes/.env)
    if not token:
        for env_path in (ENV_FILE, Path("/root/.hermes/.env")):
            try:
                if not env_path.exists():
                    continue
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("TELEGRAM_BOT_TOKEN="):
                        token = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if token:
                            break
                if token:
                    break
            except Exception:
                continue
    if not token:
        print("  [-] Telegram token tidak ditemukan -> notifikasi dilewati.")
        return
    for tgt in ({"chat_id": "5678748710"}, {"chat_id": "-1004385053126", "thread_id": 572}):
        try:
            payload = {"chat_id": tgt["chat_id"], "text": text, "parse_mode": "Markdown"}
            if "thread_id" in tgt:
                payload["message_thread_id"] = int(tgt["thread_id"])
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request("https://api.telegram.org/bot%s/sendMessage" % token,
                                         data=data,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10):
                pass
            print("  [OK] Notifikasi Telegram terkirim ke %s" % tgt["chat_id"])
        except Exception as e:
            print("  [-] Gagal kirim notifikasi: %s" % e)


def main():
    ap = argparse.ArgumentParser(description="Voratoon Daily Merit Claimer (contract-driven)")
    ap.add_argument("-t", "--token", help="Bearer token (override .env)")
    ap.add_argument("--status-only", action="store_true", help="hanya baca status")
    ap.add_argument("--no-qi", action="store_true", help="skip Resonansi Qi (push like)")
    args = ap.parse_args()

    tokens, primary, helpers = load_tokens_config(args.token)
    if not tokens:
        print("[ERROR] Tidak ada token ditemukan.")
        sys.exit(1)

    print("=" * 62)
    print("Voratoon Daily Merit Claimer")
    print("=" * 62)
    print("  Akun utama: 1 | Helper: %d" % len(helpers))
    probe_transports()

    catalog = get_catalog(primary or tokens[0])
    rules = rules_of(catalog)
    print()
    print("  KONTRAK RESMI (/cultivation/catalog):")
    for src in ("daily-login", "chapter", "comment", "comment-like", "marathon"):
        r = rules.get(src, {})
        if not r:
            continue
        cap = merit_cap_of(rules, src)
        print("    %-13s merit %-4s limit %-5s meritDailyLimit %-5s -> maks %d merit" % (
            src, r.get("merit"), r.get("dailyLimit"), r.get("meritDailyLimit"), cap))
    total_cap = sum(merit_cap_of(rules, s) for s in rules)
    print("  PLAFON MERIT/HARI PER AKUN = %d" % total_cap)
    print()

    accounts = []
    if primary:
        accounts.append({"token": primary, "label": "UTAMA"})
    for i, t in enumerate(helpers, 1):
        accounts.append({"token": t, "label": "H%d" % i})

    results = []
    for acc in accounts:
        if args.status_only:
            st, me = api_request("/cultivation/me", token=acc["token"])
            d = me.get("data", {}) if st == 200 else {}
            dy = d.get("daily", {})
            print("  %-6s Lvl %-3s merit %-7s streak %-3s | L%s C%s K%s" % (
                acc["label"], d.get("level"), d.get("merit"), d.get("streak"),
                dy.get("login", {}).get("used"), dy.get("chapters", {}).get("used"),
                dy.get("comments", {}).get("used")))
            continue
        try:
            with _hard_timeout(ACCOUNT_DEADLINE * 2):
                r = farm_one(acc["token"], rules, acc["label"], [])
            if r.get("ok"):
                r["token"] = acc["token"]
                results.append(r)
        except HardTimeout:
            print("  [ERROR] %s melewati batas waktu -> dilewati." % acc["label"])
        except Exception as e:
            print("  [ERROR] %s: %s" % (acc["label"], e))

    if not args.status_only and results and not args.no_qi:
        push_qi_likes(accounts, results)

    print()
    print("=" * 62)
    print("RINGKASAN")
    print("=" * 62)
    full = 0
    for r in results:
        d = r.get("daily", {})
        ok = (d.get("login", {}).get("used", 0) >= 1
              and d.get("chapters", {}).get("used", 0) >= 50
              and d.get("comments", {}).get("used", 0) >= 5)
        if ok:
            full += 1
        print("  %-6s Lvl %-3s merit %-7s (+%s) streak %-3s | L%s C%s K%s | like %s | %s" % (
            r["label"], r.get("level"), r.get("merit"), r.get("delta"), r.get("streak"),
            d.get("login", {}).get("used"), d.get("chapters", {}).get("used"),
            d.get("comments", {}).get("used"), r.get("likes_pushed", "-"),
            "FULL" if ok else "GAGAL"))
    print("  %d/%d akun kuota harian penuh | plafon kontrak %d merit/hari/akun"
          % (full, len(results), total_cap))

    # Notifikasi Telegram: ringkasan per akun + posisi leaderboard
    if not args.status_only and results:
        lines = ["*Laporan Harian Voratoon Daily Quest*", ""]
        total_gain = 0
        for r in results:
            d = r.get("daily", {})
            total_gain += r.get("delta") or 0
            lines.append("*%s:*" % r["label"])
            lines.append("- Level %s | Streak %s hari | Merit %s (+%s)" % (
                r.get("level"), r.get("streak"), r.get("merit"), r.get("delta")))
            lines.append("- Kuota: Login %s/1 | Bab %s/50 | Komen %s/5 | Like %s" % (
                d.get("login", {}).get("used"), d.get("chapters", {}).get("used"),
                d.get("comments", {}).get("used"), r.get("likes_pushed", "-")))
        lines.append("")
        lines.append("*Total: %d/%d akun penuh, +%s merit. Plafon kontrak %d merit/akun/hari.*"
                     % (full, len(results), "{:,}".format(total_gain), total_cap))
        try:
            st_lb, res_lb = api_request("/rankings/users", token=primary or tokens[0])
            if st_lb == 200:
                my = res_lb.get("myRank", {})
                top = res_lb.get("data", [{}])[0].get("merit", 0)
                lines.append("*Leaderboard: Rank #%s | Weekly %s | Selisih ke Top 1: %s*"
                             % (my.get("rank"), "{:,}".format(my.get("periodMerit", 0)),
                                max(0, top - (my.get("periodMerit") or 0))))
        except Exception:
            pass
        send_telegram_alert("\n".join(lines))


if __name__ == "__main__":
    main()
