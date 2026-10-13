"""Turns probe gaps and signals into ranked opportunities (gold_opportunities)."""
from __future__ import annotations
import hashlib
from collections import defaultdict
from datetime import timedelta, timezone
from geologic.datagen.reference import CLUSTER_LABELS
from geologic.facts import resolve_item
from geologic.scoring import expected_lift, rank_opportunities, response_share

CLUSTER_PAGES = {"game_day_party": "pg_deals_game_day", "sponsorship": "pg_about", "ordering": "pg_order", "value": "pg_deals",
                 "dietary": "pg_nutrition", "comparison": "pg_menu", "product": "pg_menu"}
CRAWL_PAGES = {"/order": "pg_order", "/menu": "pg_menu", "/deals": "pg_deals"}
GAP_THRESHOLD = 0.25
TREND_VELOCITY = 3.0
CITE_THRESHOLD = 0.6    # official citation rate below this triggers citation_gap
MENTION_FLOOR = 0.5     # cluster must mention LCE at least this often to be a citation_gap candidate

def _id(*parts):
    return "opp_" + hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:10]

def _window(cluster, calendar, now):
    """Active or next-within-7-days window for a cluster: (multiplier, name, expires_at)."""
    best = (1.0, None, None)
    for w in calendar:
        if cluster not in w["clusters_affected"]:
            continue
        if w["start_ts"] <= now <= w["end_ts"]:
            cand = (w["volume_multiplier"], w["name"], w["end_ts"])
        elif now < w["start_ts"] <= now + timedelta(days=7):
            cand = (w["volume_multiplier"], w["name"], w["start_ts"])
        else:
            continue
        if best[2] is None or cand[2] < best[2]:
            best = cand
    return best

def _opp(opp_type, title, *, item=None, page_id=None, persona_id=None, visual=False, conf=1.0, prompt_ids=(), signal_ids=(),
         cluster=None, gap=0.0, volume=0.0, window=(1.0, None, None), reasoning="", assets=(), status="open"):
    margin = item["margin_pct"] if item else 0.4
    available = item["available"] if item else True
    lo, hi = expected_lift(gap, volume, window[0], margin, available)
    # Cluster-derived opps share pages (comparison and product both map to pg_menu), so the cluster is part of their id.
    id_parts = (opp_type, item["item_id"] if item else page_id, persona_id)
    if opp_type in ("content_gap", "citation_gap"):
        id_parts += (cluster,)
    return dict(opp_id=_id(*id_parts), opp_type=opp_type, title=title,
                item_id=item["item_id"] if item else None, page_id=page_id, persona_id=persona_id, visual_sourced=visual,
                resolution_confidence=conf, prompt_ids=list(prompt_ids), signal_ids=list(signal_ids), cluster=cluster,
                gap_severity=round(gap, 3), expected_lift_low=lo, expected_lift_high=hi,
                question_volume=round(volume * 10 * window[0]), window_name=window[1],
                window_expires_at=window[2], reasoning=reasoning, assets=list(assets),
                status=status if available else "monitor")

def build(responses, prompts, menu, calendar, signals, now, personas=()) -> list[dict]:
    # Normalize calendar timestamps: Spark returns naive UTC datetimes; make them aware.
    cal = []
    for w in calendar:
        w = dict(w)
        for k in ("start_ts", "end_ts"):
            v = w.get(k)
            if v is not None and hasattr(v, "tzinfo") and v.tzinfo is None:
                w[k] = v.replace(tzinfo=timezone.utc)
        cal.append(w)
    calendar = cal

    P = {p["prompt_id"]: p for p in prompts}
    items = {m["item_id"]: m for m in menu}
    persona_names = {p["persona_id"]: p["display_name"] for p in personas}
    # Skip responses whose prompt is unknown (e.g. untracked or retired prompts) rather than crash.
    ok = [r for r in responses if r.get("status") == "ok" and r.get("prompt_id") in P]
    opps = []

    # S1: wrong claims per item (all prompts, not filtered by branded)
    wrong, total, wrong_prompts = defaultdict(int), defaultdict(int), defaultdict(set)
    for r in ok:
        for c in r.get("claims") or []:
            item = resolve_item(str(c.get("item", "")), menu)
            if not item or c.get("verdict") not in ("correct", "wrong"):
                continue
            total[item["item_id"]] += 1
            if c["verdict"] == "wrong":
                wrong[item["item_id"]] += 1; wrong_prompts[item["item_id"]].add(r["prompt_id"])
    for iid, n in wrong.items():
        pids = sorted(wrong_prompts[iid]); item = items[iid]
        vol = sum(P[p]["base_volume"] for p in pids)
        opps.append(_opp("accuracy_fix", f"Fix stale {item['name']} price across engines", item=item,
                         page_id=f"pg_item_{iid}", prompt_ids=pids, cluster="value", gap=n / total[iid], volume=vol,
                         reasoning=f"{n} of {total[iid]} price claims about {item['name']} are wrong.", assets=["jsonld", "faq"]))

    # S2: content_gap for low Share of Model clusters (unbranded prompts only).
    # citation_gap for clusters where LCE is mentioned but official citations are low (unbranded only).
    by_cluster_unb = defaultdict(list)
    for r in ok:
        if not P[r["prompt_id"]].get("branded", False):
            by_cluster_unb[P[r["prompt_id"]]["cluster"]].append(r)

    for cluster, rows in by_cluster_unb.items():
        share = sum(response_share(r["lce_mentioned"], r["lce_rank"]) for r in rows) / len(rows)
        mention_rate = sum(bool(r.get("lce_mentioned")) for r in rows) / len(rows)
        official_rate = sum(bool(r.get("cites_official")) for r in rows) / len(rows)
        pids = sorted({r["prompt_id"] for r in rows})
        vol = sum(P[p]["base_volume"] for p in pids)
        win = _window(cluster, calendar, now)

        if share < GAP_THRESHOLD:
            # content_gap: engines rarely surface LCE for this cluster
            assets = ["jsonld", "faq"] if cluster == "sponsorship" else ["faq"]
            opps.append(_opp("content_gap", f"Answer {cluster.replace('_', ' ')} questions", page_id=CLUSTER_PAGES[cluster],
                             prompt_ids=pids, cluster=cluster, gap=1 - share / GAP_THRESHOLD, volume=vol,
                             window=win,
                             reasoning=f"Share of Model {share:.2f} in {CLUSTER_LABELS.get(cluster, cluster)} across {len(rows)} answers.", assets=assets))
        elif mention_rate >= MENTION_FLOOR and official_rate < CITE_THRESHOLD:
            # citation_gap: LCE is mentioned but engines cite third-party sources rather than lce.com
            if cluster == "sponsorship":
                title = "AI engines credit third parties for our NFL sponsorship"
            else:
                title = f"{cluster.replace('_', ' ')} answers cite third parties, not lce.com"
            opps.append(_opp("citation_gap", title, page_id=CLUSTER_PAGES[cluster],
                             prompt_ids=pids, cluster=cluster, gap=1 - official_rate, volume=vol,
                             window=win,
                             reasoning=f"Official citation rate {official_rate:.2f} in {CLUSTER_LABELS.get(cluster, cluster)} with mention rate {mention_rate:.2f}.", assets=["jsonld", "faq"]))

    live = [s for s in signals if not s.get("quarantined")]

    # S3: persona_moment - one opp per (persona_id, item_id), aggregate signal_ids from all matching signals.
    persona_item_sigs = defaultdict(list)
    for s in live:
        if s["source_type"] == "athlete_post" and s.get("is_real_persona") and s.get("menu_item_id") and s.get("image_match_score"):
            persona_item_sigs[(s["persona_id"], s["menu_item_id"])].append(s)
    for (pid, iid), sigs in persona_item_sigs.items():
        item = items[iid]
        best = max(sigs, key=lambda s: s.get("image_match_score") or 0)
        name = persona_names.get(pid, "an NFL endorser")
        title = f"{name} posted a {item['name']} moment"
        opps.append(_opp("persona_moment", title, item=item,
                         page_id=f"pg_item_{iid}", persona_id=pid, visual=True,
                         conf=best["resolution_confidence"], signal_ids=[s["signal_id"] for s in sigs],
                         gap=0.5, volume=(best.get("reach") or 0) / 1000,
                         reasoning=f"Image matched {item['name']} at {best['image_match_score']:.2f}.", assets=["alt_text"]))

    # S5: trends
    for s in live:
        if s["source_type"] == "social" and (s.get("velocity") or 0) >= TREND_VELOCITY and s.get("menu_item_id"):
            item = items[s["menu_item_id"]]
            opps.append(_opp("trend", f"{item['name']} trend", item=item, page_id=f"pg_item_{item['item_id']}",
                             signal_ids=[s["signal_id"]], cluster="comparison", gap=min(1.0, s["velocity"] / 10),
                             volume=s.get("reach") or 0, reasoning=f"Velocity {s['velocity']}x.", assets=["description"]))

    # S7: crawler_gap - one opp per page_id, aggregate signal_ids from all zero-hit signals for that page.
    crawler_page_sigs = defaultdict(list)
    for s in live:
        if s["source_type"] == "crawler_hit" and s.get("hits") == 0 and s.get("page") in CRAWL_PAGES:
            crawler_page_sigs[s["page"]].append(s)
    for page, sigs in crawler_page_sigs.items():
        bot = next((s.get("bot") for s in sigs if s.get("bot")), "AI crawlers")
        opps.append(_opp("crawler_gap", f"AI crawlers never reach {page}", page_id=CRAWL_PAGES[page],
                         signal_ids=[s["signal_id"] for s in sigs], cluster="ordering", gap=0.8, volume=500,
                         reasoning=f"{bot} {'has' if bot != 'AI crawlers' else 'have'} not fetched {page} in 30 days.", assets=["jsonld"]))

    return rank_opportunities(opps)
