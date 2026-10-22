"""Deterministic checks on a structured draft (spec 5.4)."""
from __future__ import annotations
import json
import re
from geologic.claims import TAGGED_ATTRIBUTES, is_current, split_sentences, values_match
from geologic.facts import parse_price
from geologic.jsonld import validate_against_facts
from geologic.tiering import T0_ASSETS

COMPETITORS = ("Domino's", "Dominos", "Pizza Hut", "Papa Johns", "Papa John's")
CHECK_ORDER = ("grounded", "current", "values", "comparison", "persona", "copy", "target", "unsupported", "policy", "schema")
_NUM = re.compile(r"\$?\d+(?:\.\d{1,2})?")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")    # "1,600" joins; "12,15" stays two numbers
_HEADING = re.compile(r"^#{1,6}(?:\s+|$)")
_STANDALONE = re.compile(r"(?<![\w.])\$?\d+(?:\.\d{1,2})?(?!\w)")   # "12 people" yes, "12am" no
# The only fields build_for_page emits. Anything else in a T0 JSON-LD is free text that no fact backs.
_JSONLD_FIELDS = {"@context", "@type", "name", "url", "offers", "makesOffer", "price", "priceCurrency"}
_JSONLD_TYPES = {"MenuItem", "Offer", "Organization"}
_SITE = "https://littlecaesars.com/"


def _norm(s):
    return " ".join(str(s or "").lower().split())


def _fold(s):
    return str(s or "").replace("\u2019", "'").replace("\u2018", "'")


def _numbers(s):
    return [n for n in (parse_price(m) for m in _NUM.findall(_THOUSANDS.sub("", str(s or "")))) if n is not None]


def has_term(text, term):
    """Case-insensitive and word-bounded ("Goff's" names Goff, "Goffman" does not). Typographic apostrophes fold to
    ASCII, and the apostrophe-free spelling matches too ("dominos" for "Domino's")."""
    text, term = _fold(text), _fold(term).strip()
    if not term:
        return False
    return any(re.search(rf"(?<!\w){re.escape(x)}(?!\w)", t, re.IGNORECASE)
               for t, x in ((text, term), (text.replace("'", ""), term.replace("'", ""))) if x)


def person_terms(persons) -> tuple[str, ...]:
    """Every way a draft can name a person: the full name, the @handle and bare handle (the persona's handle if it has one,
    else the name with spaces removed), and for real people each name token of 3+ characters ("Goff"). persons are names
    or persona rows. Creator and fictional rows (is_real false) match only on full name or handle, so "Gridiron" in game
    day copy is not the creator Gridiron Grub. A plain name string, or a row
    without the is_real flag, keeps token matching (conservative)."""
    terms = set()
    for p in persons or ():
        row = p if isinstance(p, dict) else {"display_name": p}
        name = str(row.get("display_name") or row.get("name") or "").strip()
        if name:
            terms.add(name)
            if row.get("is_real") is not False:      # only an explicit non-real row drops token matching
                terms |= {t for t in re.split(r"\W+", name) if len(t) >= 3}
        for h in (row.get("handle"), re.sub(r"\W", "", name)):
            h = str(h or "").strip().lstrip("@")
            if h:
                terms |= {h, "@" + h}
    return tuple(sorted(terms, key=lambda t: (-len(t), t.lower())))


def mentions(text, terms) -> list[str]:
    return [t for t in terms if has_term(text, t)]


def _planned_terms(request, persons) -> set[str]:
    """The persona an association review was planned for. Only this person is exempt from the persona check."""
    pid, pname = request.get("persona_id"), request.get("persona_name")
    rows = [p for p in persons or () if isinstance(p, dict) and pid and p.get("persona_id") == pid]
    return {t.lower() for t in person_terms(rows + ([pname] if pname else []))}


def _all_person_terms(request, persons) -> tuple[str, ...]:
    return person_terms(list(persons or ()) + ([request["persona_name"]] if request.get("persona_name") else []))


def _units(text):
    """(kind, text, section) in order: kind is heading or sentence, and each heading opens a new section."""
    out, sec = [], 0
    for line in (text or "").splitlines():
        line = line.strip().lstrip("-* ").strip()
        if _HEADING.match(line):
            sec += 1
            h = _HEADING.sub("", line).strip()
            if h:
                out.append(("heading", h, sec))
        elif line:
            out += [("sentence", t, sec) for t in split_sentences(line)]   # "Deep!Deep! Dish" never splits a sentence
    return out


def patch_sentences(text):
    """The sentences of a patch, headings excluded (the drafter lists fact_ids per sentence; headings inherit them)."""
    return [t for k, t, _ in _units(text) if k == "sentence"]


def is_factual(sentence, names):
    return bool(_numbers(sentence)) or any(has_term(sentence, n) for n in names)


def _check(key, ok, good, bad):
    return {"key": key, "ok": bool(ok), "label": good if ok else bad}


def _target(draft, request):
    p = draft["patch"]
    return _check("target", (p["section_id"], p["op"]) == (request["section_id"], request["op"]), "Patch targets the planned section",
                  f"Patch targets {p['section_id']} {p['op']}, planned {request['section_id']} {request['op']}")


def _units_with_facts(draft):
    """Sentences carry their declared fact_ids. A heading carries its own declared ids, else every id cited in its section,
    so a number or name in a heading must match a fact cited under it."""
    declared = {_norm(s.get("text")): list(s.get("fact_ids") or []) for s in draft.get("sentences") or []}
    units = _units(draft["patch"]["text"])
    by_sec = {}
    for k, t, sec in units:
        if k == "sentence":
            by_sec.setdefault(sec, set()).update(declared.get(_norm(t), []))
    out = []
    for k, t, sec in units:
        if k == "heading":
            out.append({"text": t, "fact_ids": declared.get(_norm(t)) or sorted(by_sec.get(sec, ())), "kind": "heading"})
        else:
            ids = declared.get(_norm(t), [])
            out.append({"text": t, "fact_ids": ids, "kind": "fact" if ids else "copy"})
    return out


def _cited(ids, by_id, today, bad_ids):
    cited = []
    for fid in ids:
        f = by_id.get(fid)
        if f is None or not is_current(f, today):
            bad_ids.append(fid)
        else:
            cited.append(f)
    return cited


def _numbers_match(text, cited, quoted=()):
    allowed = [n for f in cited for n in _numbers(f["value"]) + _numbers(f.get("subject_name"))] + list(quoted)
    return all(any(abs(n - a) < 0.01 for a in allowed) for n in _numbers(text))


# A correction email or community reply must quote the wrong value it corrects ("$29.99, not $24.99"). Only those two assets,
# and only the numbers of the issue's own stated value, are allowed without a fact.
QUOTING_ASSETS = {"correction_email", "community_reply"}


def quoted_numbers(request):
    if request.get("asset_type") not in QUOTING_ASSETS:
        return []
    return _numbers((request.get("claim") or {}).get("stated_value"))


def only_quotes(text, quoted):
    """True when the text states numbers and every one of them is a quoted wrong value."""
    nums = _numbers(text)
    return bool(quoted) and bool(nums) and all(any(abs(n - q) < 0.01 for q in quoted) for n in nums)


def verify(draft, request, facts, today, *, item_names, persona_names):
    """persona_names are names or persona rows. Headings run through the same checks as sentences (kind heading)."""
    by_id = {f["fact_id"]: f for f in facts}
    sents = _units_with_facts(draft)
    people = _all_person_terms(request, persona_names)
    exempt = _planned_terms(request, persona_names) if request["asset_type"] == "association" else set()
    flagged = tuple(t for t in people if t.lower() not in exempt)
    names = tuple(item_names) + people + COMPETITORS
    quoted = quoted_numbers(request)
    ungrounded, bad_ids, mismatched, comp, named = [], [], [], [], []
    for s in sents:
        text = s["text"]
        if not s["fact_ids"] and is_factual(text, names) and not (only_quotes(text, quoted) and not any(has_term(text, n) for n in names)):
            ungrounded.append(text)
        cited = _cited(s["fact_ids"], by_id, today, bad_ids)
        if cited:
            if not _numbers_match(text, cited, quoted):
                mismatched.append(text)
            for item in (n for n in item_names if has_term(text, n)):
                if not any(item.lower() in _norm(f.get("subject_name")) or item.lower() in _norm(f["value"]) for f in cited):
                    mismatched.append(text)
        if any(has_term(text, c) for c in COMPETITORS) and _numbers(text):
            comp.append(text)
        if mentions(text, flagged):
            named.append(text)
    copies = [s for s in sents if s["kind"] == "copy"]
    t0 = request["asset_type"] in T0_ASSETS
    checks = [
        _check("grounded", not ungrounded, "Every factual sentence maps to a fact", f"{len(ungrounded)} factual sentence(s) have no fact"),
        _check("current", not bad_ids, "Every fact is current in Unity Catalog", f"Unknown or out of date fact: {', '.join(sorted(set(bad_ids)))}"),
        _check("values", not mismatched, "Numbers and names match their facts exactly", "A number or name does not match its fact"),
        _check("comparison", not comp, "No competitor prices", "States a competitor price"),
        _check("persona", not named, "No person named outside the association review", "Names a person outside the association review"),
        _check("copy", not (t0 and copies), f"{len(copies)} sentence(s) are copy, no facts" if copies else "No copy without facts",
               "Copy without facts is not allowed in T0"),
        _target(draft, request),
    ]
    return checks, sents


def jsonld_strings(text) -> list[str]:
    """Every string value in a JSON-LD document (empty if it does not parse)."""
    try:
        obj = json.loads(text)
    except (TypeError, ValueError):
        return []
    out = []

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            out.append(o)

    walk(obj)
    return out


def _jsonld_shape(obj, cited):
    """Errors for anything build_for_page would not emit, and the prices that match no cited current price fact."""
    errs, bad_prices = [], []
    names = {"little caesars"} | {_norm(f["subject_name"]) for f in cited}
    prices = [n for f in cited if f["attribute"] == "price" for n in _numbers(f["value"])]

    def walk(o, top):
        if isinstance(o, list):
            for v in o:
                walk(v, False)
            return
        if not isinstance(o, dict):
            errs.append("JSON-LD nodes must be objects")
            return
        for k, v in o.items():
            if k not in _JSONLD_FIELDS:
                errs.append(f"field {k} is not allowed in T0 JSON-LD")
            elif k in ("offers", "makesOffer"):
                walk(v, False)
            elif not isinstance(v, str):
                errs.append(f"field {k} must be text")
            elif k == "@context" and (not top or v != "https://schema.org"):
                errs.append("@context must be https://schema.org on the top node")
            elif k == "@type" and v not in _JSONLD_TYPES:
                errs.append(f"@type {v} is not allowed in T0 JSON-LD")
            elif k == "name" and _norm(v) not in names:
                errs.append(f"name {v} is not a cited fact")
            elif k == "url" and not v.startswith(_SITE):
                errs.append("url must be a littlecaesars.com page")
            elif k == "priceCurrency" and v != "USD":
                errs.append("priceCurrency must be USD")
            elif k == "price" and not (_numbers(v) and all(any(abs(n - a) < 0.01 for a in prices) for n in _numbers(v))):
                bad_prices.append(v)

    walk(obj, True)
    return errs, bad_prices


def verify_jsonld(draft, request, facts, today, *, persona_names):
    """T0 JSON-LD checks: at least one cited fact, every cited fact current, every price a cited fact's price, only the
    fields build_for_page emits, and no person or competitor in any string value. schema.org validation runs on top."""
    by_id = {f["fact_id"]: f for f in facts}
    sents = [{"text": str(s.get("text") or ""), "fact_ids": list(s.get("fact_ids") or []),
              "kind": "fact" if s.get("fact_ids") else "copy"} for s in draft.get("sentences") or []]
    bad_ids, cited = [], []
    for s in sents:
        cited += _cited(s["fact_ids"], by_id, today, bad_ids)
    text = draft["patch"]["text"]
    errs = list(validate_against_facts(text, facts, today))
    try:
        obj = json.loads(text)
    except (TypeError, ValueError):
        obj = None
    shape, bad_prices = _jsonld_shape(obj, cited) if isinstance(obj, dict) else ([], [])
    errs += [e for e in shape if e not in errs]
    mismatched = bad_prices + [s["text"] for s in sents if s["fact_ids"] and not _numbers_match(s["text"], cited)]
    strings = jsonld_strings(text) + [s["text"] for s in sents]
    terms = _all_person_terms(request, persona_names)
    named = [x for x in strings if mentions(x, terms)]
    comp = [x for x in strings if any(has_term(x, c) for c in COMPETITORS)]
    copies = [s for s in sents if s["kind"] == "copy"]
    checks = [
        _check("grounded", cited or bad_ids, "Every factual sentence maps to a fact", "JSON-LD cites no fact"),
        _check("current", not bad_ids, "Every fact is current in Unity Catalog", f"Unknown or out of date fact: {', '.join(sorted(set(bad_ids)))}"),
        _check("values", not mismatched, "Numbers and names match their facts exactly", "A number or name does not match its fact"),
        _check("comparison", not comp, "No competitor prices", "Names a competitor"),
        _check("persona", not named, "No person named outside the association review", "Names a person outside the association review"),
        _check("copy", not copies, "No copy without facts", "Copy without facts is not allowed in T0"),
        _target(draft, request),
        _check("schema", not errs, "schema.org validation passed", "; ".join(errs)),
    ]
    return checks, sents


# Descriptive facts (ordering, style, sponsorship...) are matched on their words: the judge paraphrases them ("Pizza Portal
# pickup available to order ahead" for "Pizza Portal pickup: order ahead and skip the line"). Counted facts (contents) and the
# tagged attributes keep exact matching. Brand words and function words do not count as content.
EXACT_ATTRIBUTES = set(TAGGED_ATTRIBUTES) | {"contents"}
WORD_COVERAGE = 0.6
_STOP = set("a an the and or of to in on at for with you your is are be can it its when no not from by as this that any all "
            "has have had been so through our we us their there here just also little caesars lc".split())


def _stem(w):
    for suf in ("ing", "ed", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def _content_words(s):
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", _fold(s).lower().replace("'", ""))
            if w not in _STOP and not w.isdigit() and len(w) > 1}


def _covered(texts, f):
    """For one of the texts (the stated value, then the claim text): its content words are mostly the fact's, or the fact's
    are mostly in it, and every number in it is in the fact (or is the year the fact took effect: "since 2023")."""
    fact_words = _content_words(f.get("value"))
    allowed = _numbers(f.get("value")) + _numbers(str(f.get("valid_from") or "")[:4])
    for t in texts:
        words = _content_words(t)
        if not words or not fact_words:
            continue
        common = len(words & fact_words)
        if common / len(words) < WORD_COVERAGE and common / len(fact_words) < WORD_COVERAGE:
            continue
        if all(any(abs(n - a) < 0.01 for a in allowed) for n in _numbers(t)):
            return True
    return False


def supported(claim, grounding, names=()):
    """A judge-extracted claim is supported when a grounding fact with the same attribute (and subject, when the claim has
    one) states it: numeric equality for price, serves and founded (on a
    standalone number, so "12am" is not 12), else the stated value appears in the fact value on
    token boundaries. An empty stated value is supported only when the claim text is not factual (is_factual)."""
    sv = str(claim.get("stated_value") or "").strip()
    if not sv:
        return not is_factual(str(claim.get("text") or ""), names)
    attr, subj = claim.get("attribute"), claim.get("subject")
    for f in grounding:
        if f.get("attribute") != attr or (subj and f.get("subject") != subj):
            continue
        if (attr in TAGGED_ATTRIBUTES and _STANDALONE.search(sv) and values_match(sv, f, attr)) or has_term(f["value"], sv):
            return True
    # descriptive facts: any cited one whose words cover the claim (the judge's subject and attribute labels vary for these)
    texts = [sv, str(claim.get("text") or "")]
    return any(_covered(texts, f) for f in grounding if f.get("attribute") not in EXACT_ATTRIBUTES)


def reground(patch_text, previous, facts, today, prior_ids=()):
    """Sentences for a human-edited patch (spec 5.4, Task 9 edit route). An unchanged sentence keeps its fact_ids. An
    edited sentence gets fact_ids re-derived by value matching against current brand_facts: for each number in it, the
    current facts whose value states that number, preferring facts whose subject_name the sentence names, then facts in
    prior_ids, else the single hit. No match leaves fact_ids empty, so verify() tags it copy, no facts (allowed for T1
    and T2, failed by the copy check for T0); a copy sentence that states a number or a name still fails grounded."""
    kept = {_norm(s.get("text")): list(s.get("fact_ids") or []) for s in previous or []}
    current, prior = [f for f in facts if is_current(f, today)], set(prior_ids)
    out = []
    for t in patch_sentences(patch_text):
        if _norm(t) in kept:
            out.append({"text": t, "fact_ids": kept[_norm(t)]})
            continue
        ids = set()
        for n in _numbers(t):
            hits = [f for f in current if any(abs(n - v) < 0.01 for v in _numbers(f["value"]))]
            named = [f for f in hits if f.get("subject_name") and _norm(f["subject_name"]) in _norm(t)]
            pick = named or [f for f in hits if f["fact_id"] in prior] or (hits if len(hits) == 1 else [])
            ids |= {f["fact_id"] for f in pick}
        out.append({"text": t, "fact_ids": sorted(ids)})
    return out
