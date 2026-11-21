"""Plain sentences that state this hit's decisive facts (principle 9)."""
import dates


def years(ys):
    ys = sorted(set(ys))
    return " or ".join(str(y) for y in ys)


def cand_text(c):
    ys, m, d = c
    if len(ys) == 1:
        return dates.iso((ys[0], m, d))
    return years(ys)


def hit_dob_text(h):
    if h.dob_kind == "listed":
        return "the hit's listed date of birth is " + ", ".join(cand_text(c) for c in h.dobs)
    if h.dob_kind == "listed and notes":
        return "the hit's listed and profile dates of birth are " + ", ".join(cand_text(c) for c in h.dobs)
    allys = sorted({y for c in h.dobs for y in c[0]})
    where = "profile notes" if h.dob_kind == "notes" else "search results"
    if len(h.dobs) == 1 and len(h.dobs[0][0]) > 1:
        return "the hit's %s put its birth year at %s" % (where, years(allys))
    return "the hit's %s give its date of birth as %s" % (where, ", ".join(cand_text(c) for c in h.dobs))


def hit_dob_short(h):
    if h.dob_kind in ("listed", "listed and notes"):
        return ", ".join(cand_text(c) for c in h.dobs)
    return "; ".join(cand_text(c) for c in h.dobs)


def src(s):
    return " (%s)" % s if s else ""


def clear_sentence(code, f):
    h, p = f["hit"], f["person"]
    cdob, csrc = f["dob"]
    if code == "ENTITY_TYPE_MISMATCH":
        cust, hit = f["type"]
        return "The customer is %s but the hit is %s." % (
            "a company" if cust else "an individual", "a company" if hit else "an individual")
    if code == "DECEASED":
        death, screened = f["death"]
        return "The hit's profile gives a date of death of %s, before the customer was screened on %s." % (
            dates.iso(death), dates.iso(screened))
    if code == "TEMPORAL_IMPOSSIBILITY":
        if p.entity_company():
            return "The customer was incorporated on %s%s, after the hit's earliest dated report of %s." % (
                dates.iso(cdob), src(csrc), dates.iso(f["report"]))
        return "The customer was born in %s%s, so they were at most %d when the hit's profile reports activity on %s." % (
            dates.iso(cdob) if dates.full(cdob) is False else cdob[0], src(csrc), f["age"], dates.iso(f["report"]))
    if code == "DOB_MISMATCH":
        return "The customer's date of birth is %s%s but %s." % (
            dates.iso(cdob), src(csrc), hit_dob_text(h))
    if code == "NAME_MISMATCH_VERIFIED":
        vname, vsrc = f["vname"]
        names = h.names[:3]
        more = " and %d more" % (len(h.names) - 3) if len(h.names) > 3 else ""
        if len(h.names) == 1:
            return "The customer's verified name is %s%s, which does not match the hit's name %s." % (
                vname, src(vsrc), h.names[0])
        return "The customer's verified name is %s%s, which does not match any of the hit's names %s%s." % (
            vname, src(vsrc), "; ".join(names), more)
    if code == "LOCATION_MISMATCH":
        cplaces, hplaces, _ = f["places"]
        return "The customer is linked only to %s but the hit is linked only to %s." % (
            ", ".join(sorted(cplaces)), ", ".join(hplaces))
    return ""


def agreement(f):
    h = f["hit"]
    cdob, csrc = f["dob"]
    out = []
    if f.get("dob_ok"):
        out.append("The customer's date of birth %s%s agrees with the hit's %s%s." % (
            dates.iso(cdob), src(csrc), cand_text(f["dob_match"]),
            (" from search result %s" % ", ".join(h.dob_src)) if h.dob_kind == "search" and h.dob_src else ""))
    shared = f["places"][2]
    if shared:
        out.append("Both the customer and the hit are linked to %s." % ", ".join(shared))
    ok, nsrc, hitname = f["name"]
    if ok:
        out.append("The customer's name agrees with the hit's name %s." % hitname)
    return out


def missing(f):
    """Say honestly which part could not be settled."""
    h = f["hit"]
    cdob, _ = f["dob"]
    ok = f["name"][0]
    gaps = []
    p = f.get("person")
    if p is not None and p.verified_doubt and p.unclear:
        gaps.append("identity note %s gives no result we can read, so the verified identity is unknown"
                    % p.unclear[-1][1])
    elif p is not None and p.verified_unknown():
        gaps.append("the holder named in the latest approved check cannot be read")
    elif not ok:
        gaps.append("the names do not agree closely enough to confirm")
    if not f.get("dob_ok"):
        if not h.dobs:
            gaps.append("the hit gives no date of birth to compare")
        elif not cdob:
            gaps.append("the customer has no date of birth on file")
        elif p is not None and p.verified_doubt:
            pass
        else:
            gaps.append("the dates of birth are close but do not agree")
    if f.get("loc_conflict"):
        gaps.append("their countries differ even though name and date of birth agree")
    return gaps


def write(out, alert_id):
    f = out.facts
    p = f.get("person")
    lines = []
    if out.decision == "DIFFERENT_ENTITY":
        codes = [out.code] + [c for c, _ in f["contra"] if c != out.code]
        for c in codes[:3]:
            lines.append(clear_sentence(c, f))
        if out.code == "LOCATION_MISMATCH" and f.get("ambiguous"):
            # each candidate's own countries, not only the first one's
            each = ["%s to %s" % (o.facts["person"].primary, ", ".join(sorted(o.facts["places"][0])))
                    for o in f["ambiguous"]]
            lines[0] = "Each candidate is linked only to its own countries (%s) but the hit is linked only to %s." % (
                "; ".join(each), ", ".join(f["places"][1]))
    elif out.decision == "SAME_ENTITY":
        lines += agreement(f)
        lines.append("Nothing in the customer's records contradicts the hit.")
    elif out.code == "AMBIGUOUS_CUSTOMER_RECORD":
        amb = f["ambiguous"]
        ids = ", ".join(o.facts["person"].primary for o in amb)
        lines.append("%d different customers fit alert %s (%s)." % (len(amb), alert_id, ids))
        parts = ["%s gives %s" % (o.facts["person"].primary, o.decision) for o in amb]
        lines.append("Decided one by one, %s, so the hit cannot be settled." % "; ".join(parts))
    elif f.get("shared_id"):
        lines.append("A document or registration number in the hit's identifiers matches the customer's record %s." % ", ".join(f["shared_id"]))
        lines.append("Although %s, a shared identifier means the hit cannot be cleared, so it is left for review." % clear_sentence(f["contra"][0][0], f).rstrip(".").replace("The ", "the ", 1))
    else:
        lines += agreement(f)[:2]
        gaps = missing(f)
        lines.append("Nothing in the customer's records contradicts the hit, but %s, so it can be neither cleared nor confirmed." % (
            " and ".join(gaps[:2]) if gaps else "the facts do not settle it"))
    if f.get("ambiguous") and out.code != "AMBIGUOUS_CUSTOMER_RECORD":
        amb = f["ambiguous"]
        lines.append("%d different customers fit the alert (%s) and each leads to the same decision." % (
            len(amb), ", ".join(o.facts["person"].primary for o in amb)))
    elif p is not None and len(lines) < 2:
        lines.append("The decisive records are %s." % ", ".join(out.evidence) if out.evidence
                     else "No record in the bank's systems settles it either way.")
    lines = [x for x in lines if x][:4]
    return " ".join(lines)
