"""Pipeline: load, resolve the customer per alert, gather hit facts, decide, explain."""
import collections
import sys

import reasons
import rules
from facts import HitFacts
from loader import field, load, multi
from names import Namer
from resolver import DB


def fallback(hit_id, alert_id, why):
    return {"hit_id": hit_id, "alert_id": alert_id, "decision": "REVIEW",
            "reason_code": "INSUFFICIENT_DATA", "customer_record_id": None,
            "reason": "The hit could not be assessed automatically (%s). It is left for a person to review." % why,
            "evidence": []}


def review_causes(o, h):
    """Why a hit was left for review, one or more causes per hit."""
    f = o.facts
    p = f.get("person")
    out = []
    if o.code == "AMBIGUOUS_CUSTOMER_RECORD":
        return ["several people fit"]
    if f.get("shared_id"):
        out.append("shared document identifier")
    if not h.dobs:
        out.append("no hit DOB")
    if p is not None and p.verified_unknown():
        out.append("unknown verified identity")
    if f.get("places_unread"):
        out.append("unresolved place")
    if p is not None and getattr(p, "dob_alts", None):
        out.append("ambiguous dates")
    if h.dob_unread:
        out.append("hit DOB written but unread")
    return out or ["policy review (no contradiction, no full agreement)"]


def decide(hit, alert, db, namer, people, how, stats=None):
    hid = field(hit, "hit_id", "id")
    aid = field(hit, "alert_id") or field(alert, "alert_id")
    h = HitFacts(hit, db)
    if not people:
        return {"hit_id": hid, "alert_id": aid, "decision": "REVIEW",
                "reason_code": "INSUFFICIENT_DATA", "customer_record_id": None,
                "reason": "No customer record in the system of record fits the screened details of alert %s. Without the customer's own facts the hit %s can be neither cleared nor confirmed." % (aid, h.name or hid),
                "evidence": []}
    outs = [rules.compare(h, p, alert, namer) for p in people]
    if len(outs) == 1:
        o = outs[0]
        cid = people[0].primary
    else:
        o = rules.combine(outs)
        cid = "AMBIGUOUS"
    if stats is not None and o.decision == "REVIEW":
        for cause in review_causes(o, h):
            stats["review cause: " + cause] += 1
    return {"hit_id": hid, "alert_id": aid, "decision": o.decision,
            "reason_code": o.code, "customer_record_id": cid,
            "reason": reasons.write(o, aid), "evidence": o.evidence}


def count_facts(stats, hit, h, people, how):
    """Tallies that let two data folders be compared at a glance."""
    stats["hit dob from " + (h.dob_kind or "nowhere")] += 1
    if h.dob_unread:
        stats["hit dob written but unread"] += 1
    stats["hit with country"] += bool(h.places)
    stats["hit dated reports"] += bool(h.reports)


def count_people(stats, people, how):
    stats["alert link " + ("+".join(how) if how else "none found")] += 1
    stats["alert people %s" % (len(people) if len(people) < 3 else "3+")] += 1
    for p in people:
        stats["person approved kyc checks"] += sum(1 for c in p.approved if c.kind == "kyc")
        stats["person approved note checks"] += sum(1 for c in p.approved if c.kind == "note")
        stats["person without approved check"] += not p.approved
        stats["person residence notes"] += len(p.lived)
        stats["person unreadable identity notes"] += len(p.unclear)
        stats["person dob known"] += p.dob()[0] is not None
        stats["person countries known"] += bool(p.places())


SCALARS = {
    "hits": ["hit_id", "alert_id", "entity_type", "name", "profile_notes", "deceased_date",
             "primary_category", "place_of_birth"],
    "alerts": ["alert_id", "screened_at", "customer_name", "entity_type", "dob", "country",
               "city", "account_ref", "login_handle", "email"],
    "customers": ["record_id", "entity_type", "full_name", "preferred_name", "dob", "email",
                  "phone", "nationality", "residence_country", "city", "address"],
    "kyc_checks": ["check_id", "applicant_id", "verified_name", "verified_dob", "document_country",
                   "document_number", "result", "checked_at"],
    "notes": ["note_id", "requester_email", "created_at", "text"],
}


def type_audit(data, stats):
    """A field expected to hold one value that arrives as a list or object is
    counted, so a schema change cannot quietly empty a fact."""
    for t, keys in SCALARS.items():
        for k in keys:
            odd = sum(1 for r in data[t] if isinstance(r.get(k), (list, dict)))
            if odd:
                stats["TYPE %s.%s is list or object" % (t, k)] = odd


def run(folder, stats=None):
    if stats is None:
        stats = collections.Counter()
    data = load(folder, stats)
    type_audit(data, stats)
    namer = Namer(*data["variants"])
    db = DB(data, namer)
    alerts = {}
    for a in data["alerts"]:
        alerts.setdefault(field(a, "alert_id", "id"), a)
    hits = list(data["hits"])
    seen = {field(h, "hit_id", "id") for h in hits}
    # hits named on an alert but missing from hits.jsonl still get a line
    for aid in sorted(alerts):
        for hid in multi(alerts[aid].get("hit_ids")):
            if hid not in seen:
                seen.add(hid)
                hits.append({"hit_id": hid, "alert_id": aid, "_missing": True})
    cache = {}
    rows = []
    done = set()
    for hit in hits:
        hid = field(hit, "hit_id", "id")
        if not hid or hid in done:
            continue
        done.add(hid)
        aid = field(hit, "alert_id")
        if not aid:
            aid = next((k for k in sorted(alerts) if hid in multi(alerts[k].get("hit_ids"))), "")
        try:
            if hit.get("_missing"):
                rows.append(fallback(hid, aid, "the hit profile is missing"))
                continue
            alert = alerts.get(aid)
            if alert is None:
                rows.append(fallback(hid, aid, "its alert is missing"))
                continue
            if aid not in cache:
                cache[aid] = db.resolve(alert)
                count_people(stats, *cache[aid])
            people, how = cache[aid]
            row = decide(hit, alert, db, namer, people, how, stats)
            count_facts(stats, hit, HitFacts(hit, db), people, how)
            rows.append(row)
        except Exception as e:  # one bad record must not stop the run
            stats["HIT ERRORS"] += 1
            sys.stderr.write("hit %s: %s: %s\n" % (hid, type(e).__name__, e))
            rows.append(fallback(hid, aid, "unreadable data"))
    for r in rows:
        stats["decision " + r["decision"]] += 1
    if stats["HIT ERRORS"]:
        sys.stderr.write("%d hits fell back to REVIEW because their data could not be read\n"
                         % stats["HIT ERRORS"])
    return rows
