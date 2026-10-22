#!/usr/bin/env python3
"""Top-up khusus akun yang belum FULL 695.
Idempoten: baca leaderboard harian, hanya proses yang < 695.
"""
import sys
import time

sys.path.insert(0, "/root/voratoon-bot")
from claim_daily_merit import api_request, load_tokens_config, get_catalog, rules_of

tokens, primary, helpers = load_tokens_config()
accs = ([("UTAMA", primary)] if primary else []) + [("H%d" % (i + 1), t) for i, t in enumerate(helpers)]

for rnd in range(1, 4):
    st, r = api_request("/rankings/users?period=daily&take=100", token=primary)
    byid = {}
    for u in (r.get("data") or []):
        byid[str(u.get("userId"))] = u.get("periodMerit")

    targets = []
    for lbl, tok in accs:
        st2, mm = api_request("/auth/me", token=tok)
        if st2 != 200:
            continue
        uid = str((mm.get("data") or {}).get("id"))
        pm = byid.get(uid)
        if pm is None or pm >= 695:
            continue
        need = (695 - pm + 1) // 2  # jumlah like yang kurang
        targets.append((lbl, tok, pm, need))

    if not targets:
        print("Ronde %d: semua akun sudah 695. SELESAI." % rnd)
        break

    print("Ronde %d: %d akun perlu topped-up" % (rnd, len(targets)))
    for lbl, tok, pm, need in targets:
        stc, rc = api_request("/user/comments", token=tok)
        cs = rc.get("data") or []
        ids = [c["id"] for c in cs if "id" in c]
        voters = [t for l2, t in accs if t != tok]
        got = 0
        for cid in ids:
            if got >= need:
                break
            for v in voters:
                if got >= need:
                    break
                stv, vb = api_request("/comments/%s/upvote" % cid, token=v, method="POST", body={})
                if stv == 429:
                    time.sleep(2.0)
                    continue
                if stv not in (200, 201):
                    continue
                vote = (vb.get("data") or {}).get("vote")
                if vote == 1:
                    got += 1
                elif vote is None:
                    api_request("/comments/%s/upvote" % cid, token=v, method="POST", body={})
        print("  %-6s %s -> butuh %d like, push %d" % (lbl, pm, need, got))
    time.sleep(3)

print()
print("=== VERIFIKASI AKHIR ===")
st, r = api_request("/rankings/users?period=daily&take=100", token=primary)
byid = {str(u.get("userId")): (u.get("rank"), u.get("periodMerit")) for u in (r.get("data") or [])}
full = 0
total = 0
for lbl, tok in accs:
    st2, mm = api_request("/auth/me", token=tok)
    if st2 != 200:
        continue
    total += 1
    uid = str((mm.get("data") or {}).get("id"))
    rk, pm = byid.get(uid, (None, None))
    if pm == 695:
        full += 1
    else:
        print("  %-6s rank=%-5s periodMerit=%s (kurang %s)" % (lbl, rk, pm, (695 - pm) if pm else "?"))
print("  %d/%d akun FULL 695" % (full, total))
