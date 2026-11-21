"""Read the data folder. Tolerant of missing files, bad lines and either list shape."""
import json
import os

TABLES = ["alerts", "hits", "customers", "accounts", "onboarding",
          "kyc_checks", "notes", "search_results"]


def read_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


# fields each table must offer for the engine to work; a missing one is counted
EXPECTED = {
    "alerts": ["alert_id", "screened_at", "customer_name", "entity_type", "hit_ids"],
    "hits": ["hit_id", "alert_id", "entity_type", "name"],
    "customers": ["record_id", "entity_type", "full_name", "dob", "email", "phone"],
    "accounts": ["account_id", "customer_id"],
    "onboarding": ["account_id", "customer_id", "kyc_applicant_id"],
    "kyc_checks": ["check_id", "applicant_id", "verified_name", "result", "checked_at"],
    "notes": ["note_id", "requester_email", "text"],
    "search_results": ["result_id", "query", "snippet"],
}
# the screened customer as the official alerts nest it, mapped to flat names
SCREENED = {"name": "customer_name", "full_name": "customer_name", "entity_type": "entity_type",
            "type": "entity_type", "dob": "dob", "date_of_birth": "dob", "country": "country",
            "city": "city"}


def flatten_alert(a):
    """The official alerts carry the screened details as a nested object
    ("customer": {"name", "entity_type", "dob", "country", "city"}); the CSV
    export has them flat. Both end up flat here."""
    for k in sorted(a):
        v = a[k]
        if isinstance(v, dict):
            for kk in sorted(v):
                flat = SCREENED.get(kk, kk)
                if a.get(flat) in (None, "", []):
                    a[flat] = v[kk]
    return a


def load(folder, stats=None):
    data = {}
    for t in TABLES:
        data[t] = read_jsonl(os.path.join(folder, t + ".jsonl"))
    data["alerts"] = [flatten_alert(a) for a in data["alerts"]]
    data["variants"] = read_variants(os.path.join(folder, "name_variants.json"))
    if stats is not None:
        for t in TABLES:
            stats["rows " + t] = len(data[t])
            for k in EXPECTED.get(t, []):
                miss = sum(1 for r in data[t] if r.get(k) in (None, "", []))
                if miss == len(data[t]) and data[t]:
                    stats["FIELD ABSENT %s.%s" % (t, k)] = miss
        stats["name variant groups"] = len(data["variants"][0])
        stats["legal forms"] = len(data["variants"][1])
    return data


def text(v):
    """Any scalar as a stripped string; lists joined. None becomes ""."""
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return "; ".join(text(x) for x in v if text(x))
    if isinstance(v, dict):
        return "; ".join(text(x) for _, x in sorted(v.items()) if text(x))
    if isinstance(v, bool):
        return ""
    return str(v).strip()


def multi(v):
    """A multi valued field as a list of strings, from a list or a "; " string."""
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        out = []
        for x in v:
            out.extend(multi(x))
        return out
    if isinstance(v, dict):
        out = []
        for k in sorted(v):
            out.extend(multi(v[k]))
        return out
    s = str(v).strip()
    if not s:
        return []
    return [p.strip() for p in s.split(";") if p.strip()]


def field(row, *names):
    for n in names:
        if isinstance(row, dict) and n in row:
            s = text(row[n])
            if s:
                return s
    return ""


def _lists(obj, out):
    """Collect every list of strings at any depth."""
    if isinstance(obj, dict):
        for k in sorted(obj):
            _lists(obj[k], out)
    elif isinstance(obj, list):
        strs = [x for x in obj if isinstance(x, str)]
        if strs:
            out.append(strs)
        for x in obj:
            if not isinstance(x, str):
                _lists(x, out)


FORM_HINTS = {"ltd", "gmbh", "llc", "plc", "inc"}


def read_variants(path):
    """Return (groups, legal_forms). Any nesting of string lists is accepted;
    the list that holds forms like ltd or gmbh is taken as the legal forms."""
    groups, forms = [], set()
    if not os.path.exists(path):
        return groups, forms
    try:
        with open(path, encoding="utf-8-sig") as f:
            obj = json.load(f)
    except ValueError:
        return groups, forms
    lists = []
    _lists(obj, lists)
    for lst in lists:
        clean = sorted({x.strip().lower().strip(".") for x in lst if x and x.strip()})
        if not clean:
            continue
        if len(FORM_HINTS & set(clean)) >= 2:
            forms.update(clean)
        elif len(clean) > 1:
            groups.append(clean)
    return groups, forms
