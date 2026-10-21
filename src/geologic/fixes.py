"""Fix rows: stable ids, draft requests built from issues, and the Lakebase upsert."""
from __future__ import annotations
import hashlib
import json
from geologic.claims import is_current
from geologic.issues import claim_key
from geologic.patches import get_section, last_section_id, section_containing

EXTERNAL_ASSETS = {"correction_email", "community_reply"}
ASSET_LABELS = {"jsonld": "Add structured data", "owned_patch": "Patch our page", "answer_page": "Publish an answer page",
                "moment_page": "Publish a moment FAQ", "association": "Approve the person association",
                "correction_email": "Request a correction", "community_reply": "Reply as the brand"}
CLUSTER_SUBJECTS = {"game_day_party": ("party_pack", "gameday_499", "detroit_pepperoni"),
                    "comparison": ("crazy_bread", "classic_pepperoni", "italian_cheese_bread", "slices_n_stix"),
                    "value": ("classic_pepperoni", "gameday_499", "lunch_combo", "crazy_bread"),
                    "sponsorship": (), "product": ("classic_pepperoni",), "ordering": (), "dietary": ()}
NEW_PAGE_URL = "https://littlecaesars.com/answers/{slug}"
FIX_COLUMNS = ("fix_id", "epoch", "issue_id", "issue_type", "issue_rank", "title", "lane", "asset_type", "tier", "state", "page_id",
               "section_id", "op", "section_before", "patch_text", "sentences", "grounding_fact_ids", "checks", "rationale",
               "recipient", "persona_id", "exclusion_rule_id", "prompt_ids", "agent_trace_id")
UPSERT_FIX = (f"INSERT INTO fixes ({', '.join(FIX_COLUMNS)}) VALUES ({', '.join(['%s'] * len(FIX_COLUMNS))}) "
              "ON CONFLICT (fix_id) DO UPDATE SET " + ", ".join(f"{c} = EXCLUDED.{c}" for c in FIX_COLUMNS if c != "fix_id")
              + " WHERE fixes.state IN ('pending_review', 'blocked')")
CLEAR_EPOCH_FIXES = "DELETE FROM fixes WHERE epoch = %s"


def fix_id(issue_id, asset_type):
    return "fx_" + hashlib.sha1(f"{issue_id}|{asset_type}".encode()).hexdigest()[:12]


def relevant_facts(issue, facts, today):
    subjects = {issue.get("subject"), issue.get("item_id"), "brand", *CLUSTER_SUBJECTS.get(issue.get("cluster"), ())} - {None}
    current = [f for f in facts if f["subject"] in subjects and is_current(f, today)]
    old = [f for f in facts if issue.get("subject") and f["subject"] == issue["subject"] and f["attribute"] == issue.get("attribute")
           and not is_current(f, today)]
    return current, old


def build_requests(issue, *, pages, sources, facts, prompts, claims, personas, today):
    P = {p["prompt_id"]: p for p in prompts}
    docs = {d["doc_id"]: d for d in sources}
    cur, old = relevant_facts(issue, facts, today)
    keys = set(issue.get("claim_keys") or [])
    keyed = [c for c in claims if claim_key(c["tag"], c.get("source_doc_id"), c["subject"], c["attribute"]) in keys]
    claim = {k: keyed[0][k] for k in ("text", "stated_value", "tag")} if keyed else None
    src = docs.get(issue.get("source_doc_id"))
    passage = ({"doc_id": src["doc_id"], "domain": src["domain"], "owner_class": src["owner_class"],
                "last_updated": str(src.get("last_updated")), "url": src.get("url"), "excerpt": (src.get("body") or "")[:600]}
               if src else None)
    person = next((p for p in personas if p["persona_id"] == issue.get("persona_id")), None)
    out = []
    for f in issue["planned"]:
        asset = f["asset_type"]
        page = pages.get(f["page_id"]) if f.get("page_id") else None
        body = (page or {}).get("body") or ""
        section_id, op = f.get("section_id"), f.get("op")
        if asset == "owned_patch":
            stated = (claim or {}).get("stated_value") or ""
            section_id = (section_containing(body, stated) if op == "replace" else None) or last_section_id(body) or "main"
        if asset == "jsonld":
            before = (page or {}).get("jsonld") or ""
        elif asset in EXTERNAL_ASSETS:
            before = ""
        else:
            before = get_section(body, section_id)
        out.append(dict(fix_id=fix_id(issue["issue_id"], asset), issue_id=issue["issue_id"], issue_type=issue["issue_type"],
                        issue_title=issue["title"], issue_rank=issue.get("rank"), asset_type=asset, lane=f["lane"],
                        page_id=f.get("page_id"), section_id=section_id, op=op, section_before=before, facts=cur, superseded=old,
                        prompts=[P[p]["prompt_text"] for p in issue["prompt_ids"] if p in P], claim=claim, passage=passage,
                        recipient=f.get("recipient"), persona_name=person["display_name"] if person and asset == "association" else None,
                        persona_id=issue.get("persona_id"), prompt_ids=list(issue["prompt_ids"])))
    return out


def fix_values(req, final, epoch, trace_id):
    row = {"fix_id": req["fix_id"], "epoch": epoch, "issue_id": req["issue_id"], "issue_type": req["issue_type"],
           "issue_rank": req.get("issue_rank"), "title": f"{ASSET_LABELS[req['asset_type']]}: {req['issue_title']}",
           "lane": req["lane"], "asset_type": req["asset_type"], "tier": final["tier"], "state": final["state"],
           "page_id": req.get("page_id"), "section_id": final["patch"]["section_id"], "op": final["patch"]["op"],
           "section_before": req.get("section_before"), "patch_text": final["patch"]["text"],
           "sentences": json.dumps(final["sentences"]), "grounding_fact_ids": final["grounding_fact_ids"],
           "checks": json.dumps(final["checks"]), "rationale": final.get("rationale"), "recipient": req.get("recipient"),
           "persona_id": req.get("persona_id"), "exclusion_rule_id": final.get("exclusion_rule_id"),
           "prompt_ids": req["prompt_ids"], "agent_trace_id": trace_id}
    return tuple(row[c] for c in FIX_COLUMNS)
