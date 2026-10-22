#!/usr/bin/env python3
"""Audit status kuota harian semua akun Voratoon (read-only, tidak claiming)."""
import sys

sys.path.insert(0, "/home/dede/voratoon-bot")
from merit_farmer import api_request, load_tokens_config

tokens, primary, helpers = load_tokens_config()
akun = [("UTAMA", primary)] + [("H%d" % i, t) for i, t in enumerate(helpers, 1)]

full = 0
total = 0
belum = []
rows = []

for label, tok in akun:
    if not tok:
        continue
    total += 1
    st, me = api_request("/cultivation/me", token=tok)
    if st != 200:
        belum.append((label, "token status %s" % st))
        rows.append("%-6s TOKEN TIDAK VALID (%s)" % (label, st))
        continue
    d = me.get("data", {})
    daily = d.get("daily", {})
    l = daily.get("login", {}).get("used", 0)
    c = daily.get("chapters", {}).get("used", 0)
    k = daily.get("comments", {}).get("used", 0)
    ok = l >= 1 and c >= 50 and k >= 5
    if ok:
        full += 1
    else:
        belum.append((label, "L%d/C%d/K%d" % (l, c, k)))
    rows.append(
        "%-6s Lvl %-3s Merit %-7s | Login %s | Bab %-3s | Komen %-2s | %s"
        % (label, d.get("level"), d.get("merit"), l, c, k, "FULL" if ok else "GAGAL")
    )

for r in rows:
    print(r)
print()
print("RESULT: %d/%d akun kuota harian LENGKAP (Login 1, Bab 50, Komen 5)" % (full, total))
if belum:
    print("BELUM LENGKAP:")
    for b in belum:
        print("  - %s : %s" % b)
