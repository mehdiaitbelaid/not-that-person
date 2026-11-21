"""Compare one customer with one hit (principles 6 and 7)."""
import dates
from facts import is_company, kind
from loader import field

# order used to pick the main code when several contradictions hold
CLEAR_ORDER = ["ENTITY_TYPE_MISMATCH", "DECEASED", "TEMPORAL_IMPOSSIBILITY",
               "DOB_MISMATCH", "LOCATION_MISMATCH", "NAME_MISMATCH_VERIFIED"]

CODES = {
    "DIFFERENT_ENTITY": {"TEMPORAL_IMPOSSIBILITY", "DOB_MISMATCH", "LOCATION_MISMATCH",
                         "NAME_MISMATCH_VERIFIED", "ENTITY_TYPE_MISMATCH", "DECEASED"},
    "SAME_ENTITY": {"NAME_DOB_LOCATION_MATCH", "NAME_DOB_MATCH", "NAME_LOCATION_MATCH"},
    "REVIEW": {"INSUFFICIENT_DATA", "AMBIGUOUS_CUSTOMER_RECORD"},
}


class Outcome:
    def __init__(self, decision, code, evidence, facts):
        self.decision, self.code = decision, code
        self.evidence = sorted(set(e for e in evidence if e))
        self.facts = facts


def dob_contradicted(cdob, cand):
    """Principle 6: birth year more than 1 year outside, or same year with a
    different month or day where both give one."""
    ys, m, d = cand
    cy = cdob[0]
    if cy < min(ys) - 1 or cy > max(ys) + 1:
        return True
    if len(ys) == 1 and cy == ys[0] and m and cdob[1]:
        if m != cdob[1]:
            return True
        if d and cdob[2] and d != cdob[2]:
            return True
    return False


def dob_agrees(cdob, cand):
    """Principle 7: the birth year is one of the hit's possible years and every
    part both give is equal."""
    ys, m, d = cand
    if cdob[0] not in ys:
        return False
    if m and cdob[1] and m != cdob[1]:
        return False
    if d and cdob[2] and d != cdob[2]:
        return False
    return True


def possible_agreement(h, p, alert, namer, company):
    """When the verified identity cannot be read, any name and any date of birth
    the customer might have (records, screened details, approved checks, notes we
    could not classify) that agree with the hit keep a location difference from
    clearing."""
    if company:
        return False
    names = [n for n, _ in p.record_names()] + [c.name for c in p.checks if c.name]
    names += p.loose_names + [field(alert, "customer_name")]
    name_hit = any(namer.compare(n, x, False) for n in names if n for x in h.names)
    if not name_hit:
        return False
    if h.dob_unread or not h.dobs:
        return True
    ds = list(p.loose_dobs) + [c.dob for c in p.checks if c.dob]
    for r in p.records:
        raw = field(r, "dob")
        ds += dates.readings(raw) if dates.ambiguous(raw) else [d for d in [dates.parse(raw)] if d]
    sraw = field(alert, "dob")
    ds += dates.readings(sraw) if dates.ambiguous(sraw) else [d for d in [dates.parse(sraw)] if d]
    return any(dob_agrees(d, c) for d in ds for c in h.dobs)


def completion_confirms(h, p, namer, reads):
    """The hit name that the newest completion only note's holder agrees with,
    when its date of birth agrees too; otherwise None."""
    if not p.completed or p.unclear:
        return None
    c = p.completed[-1]
    if not any(dob_agrees(c.dob, x) for x in h.dobs):
        return None
    return next((n for n in h.names if namer.compare(c.name, n, False)), None)


def compare(h, p, alert, namer):
    """Return an Outcome for hit facts h against Person p."""
    f = {"hit": h, "person": p}
    contra = []
    cust_company = p.entity_company()
    if cust_company is None:
        cust_company = kind(field(alert, "entity_type"))
    company = bool(cust_company)
    f["company"] = company

    # type: an unknown or unrecognised type on either side is never a mismatch
    if h.type_known and cust_company is not None and cust_company != h.company:
        contra.append(("ENTITY_TYPE_MISMATCH", [p.primary]))
        f["type"] = (cust_company, h.company)

    # death before screening
    screened = dates.parse(field(alert, "screened_at"))
    # every reading of the death date must fall before the screening, each at its
    # latest possible day
    if h.deaths and screened and all(dates.latest(d) < dates.earliest(screened) for d in h.deaths):
        # the deciding fact is the hit's own death date, set against the screening
        # of this customer record
        contra.append(("DECEASED", [h.id + "#" + h.death_src, p.primary]))
        f["death"] = (h.death, screened)

    cdob, csrc = p.dob()
    # a numeric date whose day and month could swap is carried in both readings;
    # a contradiction must hold under every reading
    reads = p.dob_readings() if cdob else []
    doubt = p.verified_doubt
    f["dob"] = (cdob, csrc)

    # time: younger than 16 at the earliest dated report, or not yet incorporated
    if cdob and h.reports and not doubt:
        first = h.reports[0]
        f["report"] = first
        if company:
            if all(dates.earliest(r) > dates.latest(first) for r in reads):
                contra.append(("TEMPORAL_IMPOSSIBILITY", [csrc]))
        else:
            age = max(dates.max_age(r, first) for r in reads)
            # the organisers count by birth year too ("born in 2007 ... at most 13"),
            # so both the dated age and the year difference must be under 16
            years = max(first[0] - r[0] for r in reads)
            f["age"] = years
            if age < 16 and years < 16:
                contra.append(("TEMPORAL_IMPOSSIBILITY", [csrc]))

    # date of birth: one agreeing date is enough to agree, and every date the hit
    # gives must be contradicted to clear
    # a labelled date (a "DOB:" line, a register extract) never clears or confirms,
    # but one it does not contradict stops the clearance
    label_ok = any(not dob_contradicted(r, c) for r in reads for c in h.label_dobs)
    f["label_agrees"] = any(dob_agrees(r, c) for r in reads for c in h.label_dobs)
    dob_ok, f["dob_match"] = False, None
    if cdob and h.dobs:
        match = next((c for c in h.dobs if dob_agrees(cdob, c)), None)
        dob_ok = match is not None
        f["dob_match"] = match
        any_read_ok = any(dob_agrees(r, c) for r in reads for c in h.dobs)
        f["dob_any_reading"] = any_read_ok
        if not h.dob_unread and not doubt and not label_ok and \
                all(dob_contradicted(r, c) for r in reads for c in h.dobs):
            contra.append(("DOB_MISMATCH", [csrc] + h.dob_src))

    # names: the verified legal name outranks the record and the screened name
    vname, vsrc = p.verified_name()
    name_ok, name_src, name_hit = False, None, None
    if vname:
        enough = namer.real(vname, company) >= (1 if company else 2)
        verdicts = [(namer.compare(vname, n, company), n) for n in h.names]
        hitname = next((n for v, n in verdicts if v), None)
        if enough and hitname:
            name_ok, name_src, name_hit = True, vsrc, hitname
        # principle 8: a hit name in a script the verified name does not share
        # cannot be compared, so it alone never makes a mismatch; at least one
        # comparable hit name must disagree
        unknown = not any(v is False for v, _ in verdicts)
        if enough and not hitname and h.names and not unknown and not p.verified_doubt:
            contra.append(("NAME_MISMATCH_VERIFIED", [vsrc]))
        f["vname"] = (vname, vsrc)
    elif not p.verified_unknown():
        # declared names stand in only when no verified identity could exist
        for n, rid in p.record_names():
            if namer.real(n, company) < (1 if company else 2):
                continue
            hitname = next((x for x in h.names if namer.compare(n, x, company)), None)
            if hitname:
                name_ok, name_src, name_hit = True, rid, hitname
                break
    f["name"] = (name_ok, name_src, name_hit)

    # location
    cplaces = p.places()
    shared = sorted(set(cplaces) & h.places)
    f["places"] = (cplaces, sorted(h.places), shared)
    loc_src = []
    blocked = bool(h.places_unread or p.places_unread)
    f["places_unread"] = blocked
    if cplaces and h.places and not shared and blocked:
        # the known countries differ; an unresolved place only stops the clearance,
        # it never turns this into a confirmation
        f["loc_conflict"] = True
    if cplaces and h.places and not shared and not blocked:
        loc_src = sorted({s for v in cplaces.values() for s in v})
        # principle 6: a country difference does not clear a name and DOB agreement
        # an unreadable hit date of birth might be the agreement, so it blocks too
        possible = possible_agreement(h, p, alert, namer, company) if p.verified_unknown() else False
        f["possible_agreement"] = possible
        # an identity we cannot read may be the one that agrees, so no location
        # clearance rests on it
        veto = p.verified_unknown()
        f["loc_veto"] = veto
        if veto:
            f["loc_conflict"] = True
        # principle 6 applies to companies too: an incorporation date is their
        # date of birth; a labelled date that agrees also stops the clearance
        elif not (name_ok and (dob_ok or f.get("dob_any_reading") or f.get("label_agrees") or h.dob_unread)) \
                and not possible:
            contra.append(("LOCATION_MISMATCH", loc_src))
        else:
            f["loc_conflict"] = True

    f["dob_ok"] = dob_ok
    f["contra"] = contra
    # a document or registration number shared with the hit outweighs any
    # contradiction: such a hit is never cleared
    docs = p.documents()
    shared_id = sorted(docs[i] for i in h.idents if i in docs)
    if contra and shared_id:
        f["shared_id"] = shared_id
        return Outcome("REVIEW", "INSUFFICIENT_DATA", shared_id, f)
    if contra:
        contra.sort(key=lambda c: CLEAR_ORDER.index(c[0]))
        ev = [e for _, src in contra for e in src]
        return Outcome("DIFFERENT_ENTITY", contra[0][0], ev, f)

    shared_src = sorted({s for c in shared for s in cplaces[c]})
    if company:
        if name_ok and shared:
            return Outcome("SAME_ENTITY", "NAME_LOCATION_MATCH",
                           [name_src] + shared_src, f)
    elif not name_ok and not contra and not f.get("loc_conflict") and completion_confirms(h, p, namer, reads):
        # principle 7 on a completion only note: it may confirm, never clear
        c = p.completed[-1]
        f["name"] = (True, c.id, completion_confirms(h, p, namer, reads))
        f["dob"] = (c.dob, c.id)
        f["dob_ok"] = True
        f["dob_match"] = next((x for x in h.dobs if dob_agrees(c.dob, x)), None)
        code = "NAME_DOB_LOCATION_MATCH" if shared else "NAME_DOB_MATCH"
        return Outcome("SAME_ENTITY", code, [c.id] + h.dob_src + shared_src, f)
    elif name_ok and dob_ok and not f.get("loc_conflict"):
        ev = [csrc] + h.dob_src + shared_src
        code = "NAME_DOB_LOCATION_MATCH" if shared else "NAME_DOB_MATCH"
        return Outcome("SAME_ENTITY", code, ev, f)
    # reference reviews cite what ties both sides together; when nothing else
    # does, the record or check that gave the agreeing name is cited
    ev = []
    if shared:
        ev += shared_src
    if dob_ok:
        ev.append(csrc)
    if not ev and name_ok:
        ev.append(name_src)
    return Outcome("REVIEW", "INSUFFICIENT_DATA", ev, f)


def combine(outcomes):
    """Principle 3: several people fit. Same decision for all gives it; otherwise
    REVIEW with AMBIGUOUS_CUSTOMER_RECORD."""
    decisions = {o.decision for o in outcomes}
    ev = sorted({e for o in outcomes for e in o.evidence})
    if len(decisions) == 1:
        o = outcomes[0]
        return Outcome(o.decision, o.code, ev, dict(o.facts, ambiguous=outcomes))
    ids = [o.facts["person"].primary for o in outcomes]
    return Outcome("REVIEW", "AMBIGUOUS_CUSTOMER_RECORD", ids,
                   dict(outcomes[0].facts, ambiguous=outcomes))
