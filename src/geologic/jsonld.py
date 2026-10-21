"""Minimal schema.org validation for the asset types GEOlogic publishes."""
from __future__ import annotations
import json
from geologic.claims import is_current
from geologic.facts import resolve_item

_SUPPORTED = {"MenuItem", "Offer", "Organization", "FAQPage"}

def validate(jsonld, menu: list[dict]) -> list[str]:
    if jsonld is None:
        return ["missing JSON-LD"]
    if isinstance(jsonld, str):
        try:
            obj = json.loads(jsonld)
        except json.JSONDecodeError:
            return ["invalid JSON"]
    else:
        obj = jsonld
    t = obj.get("@type")
    if t not in _SUPPORTED:
        return [f"unsupported @type {t}"]
    errs: list[str] = []
    if t == "MenuItem":
        item = resolve_item(obj.get("name", ""), menu)
        if item is None:
            errs.append(f"unknown menu item {obj.get('name')}")
        offer = obj.get("offers")
        if offer:
            if offer.get("priceCurrency") != "USD":
                errs.append("priceCurrency must be USD")
            if item is not None:
                try:
                    p = float(offer.get("price"))
                except (TypeError, ValueError):
                    errs.append("offer price is not a number")
                else:
                    if abs(p - item["price"]) >= 0.01:
                        errs.append(f"offer price {p:.2f} does not match menu price {item['price']:.2f}")
    if t == "FAQPage":
        ents = obj.get("mainEntity") or []
        if not ents or not all(e.get("name") and (e.get("acceptedAnswer") or {}).get("text") for e in ents):
            errs.append("FAQPage needs questions with accepted answers")
    return errs


def _menu_from_facts(facts, today):
    return [{"name": f["subject_name"], "price": float(f["value"]), "aliases": []}
            for f in facts if f["attribute"] == "price" and is_current(f, today)]


def validate_against_facts(jsonld, facts, today):
    return validate(jsonld, _menu_from_facts(facts, today))


def build_for_page(page, facts, today):
    """Deterministic T0 draft: JSON-LD for an owned page from current brand_facts only (no LLM)."""
    subj = page.get("primary_subject")
    price = next((f for f in facts if f["subject"] == subj and f["attribute"] == "price" and is_current(f, today)), None)
    if price is None:
        raise ValueError(f"no current price fact for {subj}")
    offer = {"@type": "Offer", "name": price["subject_name"], "price": price["value"], "priceCurrency": "USD"}
    if page.get("page_type") == "deals":
        obj = {"@context": "https://schema.org", "@type": "Organization", "name": "Little Caesars", "url": page["url"], "makesOffer": [offer]}
    else:
        obj = {"@context": "https://schema.org", "@type": "MenuItem", "name": price["subject_name"],
               "offers": {k: v for k, v in offer.items() if k != "name"}}
    return {"patch": {"section_id": "jsonld", "op": "replace", "text": json.dumps(obj, separators=(",", ":"))},
            "sentences": [{"text": f"{price['subject_name']} costs ${price['value']}.", "fact_ids": [price["fact_id"]]}],
            "rationale": "Structured data so engines read the current price from our page."}
