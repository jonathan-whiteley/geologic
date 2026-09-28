"""Minimal schema.org validation for the asset types GEOlogic publishes."""
from __future__ import annotations
import json
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
