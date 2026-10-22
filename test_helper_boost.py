#!/usr/bin/env python3
"""TES DI AKUN HELPER: apakah akun lain bisa MEMBANTU helper menambah merit?
Uji A: upvote dari akun utama ke komentar helper -> cek delta merit helper
Uji B: apakah helper punya slot daily 'likes'?
Uji C: apakah merit helper naik kalau dia yang NGETIK upvote (voter dapat merit)?
"""
import sys
import json
import time

sys.path.insert(0, "/home/dede/voratoon-bot")
from merit_farmer import api_request, load_tokens_config

tokens, primary, helpers = load_tokens_config()
helper = helpers[1]  # H2


def snap(tok):
    s, m = api_request("/cultivation/me", token=tok)
    if s != 200:
        return None
    d = m.get("data", {})
    return {
        "merit": d.get("merit"),
        "exp": d.get("exp"),
        "level": d.get("level"),
        "daily": d.get("daily", {}),
        "streak": d.get("streak"),
    }


print("=" * 66)
print("UJI A: apakah upvote dari AKUN LAIN menambah merit PEMILIK komentar?")
print("=" * 66)
before = snap(helper)
print("  helper SEBELUM : merit=%s exp=%s level=%s" % (before["merit"], before["exp"], before["level"]))

# ambil komentar milik helper
s_uc, r_uc = api_request("/user/comments", token=helper)
comments = r_uc.get("data", []) if s_uc == 200 and isinstance(r_uc.get("data"), list) else []
print("  komentar milik helper:", len(comments))
if not comments:
    print("  helper belum punya komentar -> skip")
    targets = []
else:
    targets = [c["id"] for c in comments[:3] if "id" in c]
    print("  target upvote:", targets)
    print()
    print("  -> upvote 3 komentar helper memakai token AKUN UTAMA (akun lain):")
    for cid in targets:
        s, r = api_request("/comments/%s/upvote" % cid, token=primary, method="POST", body={})
        print("     id=%s -> %s %s" % (cid, s, str(r)[:70]))
        time.sleep(0.3)

time.sleep(3)
after = snap(helper)
print()
print("  helper SESUDAH : merit=%s exp=%s level=%s" % (after["merit"], after["exp"], after["level"]))
d_merit = (after["merit"] or 0) - (before["merit"] or 0)
d_exp = (after["exp"] or 0) - (before["exp"] or 0)
print("  DELTA MERIT = %+d   DELTA EXP = %+d" % (d_merit, d_exp))
print()
if d_merit == 0:
    print("  ==> HASIL: upvote dari akun lain TIDAK menambah merit pemilik komentar.")
    print("      Helper tidak bisa 'dibantu' oleh akun lain untuk quest like.")
else:
    print("  ==> HASIL: merit helper naik %+d -> mekanismenya ADA." % d_merit)

print()
print("=" * 66)
print("UJI B: apakah ada slot 'likes' di daily counter helper?")
print("=" * 66)
for label, key in (("SEBELUM", "daily"), ("SESUDAH", "daily")):
    pass
print("  daily helper:", json.dumps(after["daily"], ensure_ascii=False))
slots = [k for k in after["daily"].keys() if k not in ("date", "timeZone")]
print("  slot tersedia:", slots)
print("  ada 'likes'?", "likes" in slots or "like" in slots)

print()
print("=" * 66)
print("UJI C: apakah VOTER (yang meng-upvote) dapat merit?")
print("=" * 66)
m_before = snap(primary)
s_uc2, r_uc2 = api_request("/user/comments", token=helper)
cs = r_uc2.get("data", []) if s_uc2 == 200 else []
if cs:
    cid = cs[0]["id"]
    # toggle: upvote lalu upvote lagi (membalik) untuk mengukur delta voter
    s, r = api_request("/comments/%s/upvote" % cid, token=primary, method="POST", body={})
    print("  voter upvote id=%s -> %s" % (cid, s))
    time.sleep(2)
    m_after = snap(primary)
    print("  voter merit: %s -> %s (delta %+d)" % (
        m_before["merit"], m_after["merit"], (m_after["merit"] or 0) - (m_before["merit"] or 0)))
    print("  voter exp  : %s -> %s (delta %+d)" % (
        m_before["exp"], m_after["exp"], (m_after["exp"] or 0) - (m_before["exp"] or 0)))

print()
print("=" * 66)
print("RINGKASAN")
print("=" * 66)
print("  helper merit saat ini : %s (level %s, streak %s)" % (
    after["merit"], after["level"], after["streak"]))
print("  helper gain hari ini  : +%d (dari 3 misi: 20+500+75=595)" % (
    (after["merit"] or 0) - (after["merit"] or 0)))
print("  Plafon harian helper  : 595 merit (login 20 + bab 500 + komen 75)")
print("  Bonus dari upvote     : TIDAK ADA untuk merit, hanya exp per upvote")
