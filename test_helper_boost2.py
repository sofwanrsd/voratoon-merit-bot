#!/usr/bin/env python3
"""UJI LANJUTAN di akun helper: apakah bonus upvote punya batas harian?
Kalau tidak ada cap, semua helper bisa saling upvote tanpa batas.
Kalau ada cap, kita cari batasnya."""
import sys
import json
import time

sys.path.insert(0, "/home/dede/voratoon-bot")
from merit_farmer import api_request, load_tokens_config

tokens, primary, helpers = load_tokens_config()
helper = helpers[1]  # H2


def merit_of(tok):
    s, m = api_request("/cultivation/me", token=tok)
    if s != 200:
        return None
    return (m.get("data", {}).get("merit") or 0)


# Ambil semua komentar helper
s_uc, r_uc = api_request("/user/comments", token=helper)
comments = r_uc.get("data", []) if s_uc == 200 and isinstance(r_uc.get("data"), list) else []
targets = [c["id"] for c in comments if "id" in c]
print("komentar helper tersedia:", len(targets))
print("votes per komentar SEBELUM:")
for c in comments[:12]:
    v = c.get("data", {}).get("votes", {})
    print("   id=%-8s %s" % (c.get("id"), v))

before = merit_of(helper)
print("\nhelper merit sebelum:", before)

# Uji: upvote 10 komentar helper dengan 2 akun lain (main + H1), lalu cek delta
print("\n=== UJI: 10 upvote dari 2 akun lain (main + H1) ===")
voters = [primary, helpers[0]]
count = 0
for cid in targets[:10]:
    for vtok in voters:
        s, r = api_request("/comments/%s/upvote" % cid, token=vtok, method="POST", body={})
        count += 1
        time.sleep(0.12)
time.sleep(3)
after = merit_of(helper)
print("total upvote dikirim:", count)
print("helper merit:", before, "->", after, "| DELTA = %+d" % ((after or 0) - (before or 0)))
if count:
    print("merit per upvote ~ %.2f" % (((after or 0) - (before or 0)) / count))

print("\n=== UJI: apakah ada batas? kirim 40 upvote lagi ===")
before2 = merit_of(helper)
sent = 0
for cid in targets:
    for vtok in voters:
        s, r = api_request("/comments/%s/upvote" % cid, token=vtok, method="POST", body={})
        if s in (200, 201):
            sent += 1
        time.sleep(0.08)
time.sleep(3)
after2 = merit_of(helper)
print("upvote dikirim:", sent)
print("helper merit:", before2, "->", after2, "| DELTA = %+d" % ((after2 or 0) - (before2 or 0)))
print("merit per upvote ~ %.2f" % (((after2 or 0) - (before2 or 0)) / max(1, sent)))

print("\n=== CEK votes terbaru helper ===")
s_uc2, r_uc2 = api_request("/user/comments", token=helper)
cs = r_uc2.get("data", []) if s_uc2 == 200 else []
for c in cs[:6]:
    print("   id=%-8s %s" % (c.get("id"), c.get("data", {}).get("votes", {})))

print("\n=== RINGKASAN ===")
print("  total merit gained helper dari semua upvote:", (after2 or 0) - (before or 0))
print("  bandingan: 1 hari misi penuh = 595 merit")
print("  1 upvote = ? merit ; 50 upvote = ? merit")
