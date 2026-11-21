"""Partial dates. A date is (year, month, day) with None for an unknown part."""
import re

MONTHS = {}
for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                       "august", "september", "october", "november", "december"], 1):
    MONTHS[m] = i
    MONTHS[m[:3]] = i
MONTHS["sept"] = 9

MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
YEAR = r"(1[89]\d\d|20\d\d)"


def mon(g):
    g = g.rstrip(".")
    return MONTHS.get(g, MONTHS.get(g[:3]))


def ok(y, m, d):
    if y is not None and not 1800 <= y <= 2100:
        return False
    if m is not None and not 1 <= m <= 12:
        return False
    if d is not None and not 1 <= d <= 31:
        return False
    return True


def parse(s):
    """Parse one date written in any of the common forms. None if unparsed."""
    if s is None:
        return None
    s = str(s).strip().lower().rstrip(".")
    if not s:
        return None
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s)
    s = re.sub(r"^(?:the|on)\s+", "", s)
    s = re.sub(r"t\d\d:\d\d.*$", "", s)
    pats = [
        (r"^(\d{4})-(\d{1,2})-(\d{1,2})$", "ymd"),
        (r"^(\d{4})/(\d{1,2})/(\d{1,2})$", "ymd"),
        (r"^(\d{4})-(\d{1,2})$", "ym"),
        (r"^(\d{4})/(\d{1,2})$", "ym"),
        (r"^(\d{4})$", "y"),
        (r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})$", "dmy"),
        (r"^(\d{1,2})[ \-](?:of )?" + MON + r"[ ,\-]+(\d{4})$", "dMy"),
        (r"^" + MON + r"[ \-](\d{1,2}),?[ ]+(\d{4})$", "Mdy"),
        (r"^" + MON + r",?[ \-]+(?:of )?(\d{4})$", "My"),
        (r"^(\d{1,2})[/.\-](\d{4})$", "my"),
    ]
    for p, kind in pats:
        m = re.match(p, s)
        if not m:
            continue
        g = m.groups()
        y = mo = d = None
        if kind == "ymd":
            y, mo, d = int(g[0]), int(g[1]), int(g[2])
        elif kind == "ym":
            y, mo = int(g[0]), int(g[1])
        elif kind == "y":
            y = int(g[0])
        elif kind == "dmy":
            # the bank writes slashed dates day first; a first part over 12 confirms it
            a, b = int(g[0]), int(g[1])
            if b > 12 and a <= 12:
                a, b = b, a
            d, mo, y = a, b, int(g[2])
        elif kind == "dMy":
            d, mo, y = int(g[0]), mon(g[1]), int(g[2])
        elif kind == "Mdy":
            mo, d, y = mon(g[0]), int(g[1]), int(g[2])
        elif kind == "My":
            mo, y = mon(g[0]), int(g[1])
        elif kind == "my":
            mo, y = int(g[0]), int(g[1])
        if ok(y, mo, d):
            return (y, mo, d)
    return None


def find_all(s):
    """Every date written inside free text, in order, as (start, end, date)."""
    out = []
    if not s:
        return out
    t = s.lower()
    pats = [
        r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b",
        r"\b(\d{4})/(\d{1,2})/(\d{1,2})\b",
        r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b",
        r"\b(\d{1,2})(?:st|nd|rd|th)?[ \-](?:of )?" + MON + r",?[ \-](\d{4})\b",
        r"\b" + MON + r" (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})\b",
        r"\b" + MON + r",? (?:of )?(\d{4})\b",
        r"\b(\d{4})-(\d{1,2})\b(?![\-/]\d)",
        r"\b" + YEAR + r"\b",
    ]
    taken = []
    for p in pats:
        for m in re.finditer(p, t):
            a, b = m.span()
            if any(a < y and b > x for x, y in taken):
                continue
            d = parse(re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", m.group(0)))
            if d:
                taken.append((a, b))
                out.append((a, b, d))
    out.sort()
    return out


def iso(d):
    if not d:
        return ""
    y, m, dd = d
    if m is None:
        return "%04d" % y
    if dd is None:
        return "%04d-%02d" % (y, m)
    return "%04d-%02d-%02d" % (y, m, dd)


def full(d):
    return bool(d) and None not in d


def compatible(a, b):
    """Equal in every part both give."""
    if not a or not b:
        return True
    return all(x is None or y is None or x == y for x, y in zip(a, b))


def latest(d):
    """Latest possible (y, m, d) a partial date can mean."""
    y, m, dd = d
    m2 = m if m is not None else 12
    d2 = dd if dd is not None else 31
    return (y, m2, d2)


def earliest(d):
    y, m, dd = d
    return (y, m if m is not None else 1, dd if dd is not None else 1)


def max_age(birth, when):
    """Oldest the person could be on date `when` (both partial)."""
    b = earliest(birth)
    w = latest(when)
    age = w[0] - b[0]
    if (w[1], w[2]) < (b[1], b[2]):
        age -= 1
    return age


SLASHED = re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b")


def ambiguous(raw):
    """A day first numeric date where day and month could swap (both 12 or under
    and different). The bank writes day first, but a contradiction must not rest
    on that reading, so callers keep only the year for clearing."""
    m = SLASHED.search(str(raw or ""))
    if not m:
        return False
    a, b = int(m.group(1)), int(m.group(2))
    return a <= 12 and b <= 12 and a != b


RANGE = re.compile(r"^\s*(?:between\s+)?(\d{4})\s*(?:-|\u2013|\u2014|to|until|and)\s*(\d{4})\s*$", re.I)
CIRCA = re.compile(r"^\s*(?:circa|ca\.?|c\.|about|approx\.?|approximately|around|abt\.?|~)\s*", re.I)
ALTS = re.compile(r"\s*(?:\bor\b|/|;|,|\|)\s*", re.I)


def readings(raw):
    """Every full reading of one written date. A numeric date whose day and month
    could swap gives both; anything else gives its one parse, or nothing."""
    d = parse(raw)
    if not d:
        return []
    m = SLASHED.search(str(raw or ""))
    if m and ambiguous(raw):
        a, b = int(m.group(1)), int(m.group(2))
        return [(d[0], b, a), (d[0], a, b)]
    return [d]


def parse_hits(s):
    """A hit's birth date entry as a list of candidates (years, month, day).
    A range gives every year in it as one candidate; alternatives ("1950 or 1980",
    "1950/1980") and the two readings of an ambiguous numeric date give one
    candidate each. An empty list means it cannot be read with certainty."""
    s = str(s or "").strip()
    m = RANGE.match(s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if 1800 <= a <= b <= 2100 and b - a <= 30:
            return [(list(range(a, b + 1)), None, None)]
        return []
    s = CIRCA.sub("", s)
    if parse(s) is None and ALTS.search(s):
        parts = [x for x in ALTS.split(s) if x.strip()]
        out = []
        for x in parts:
            got = parse_hits(x)
            if not got:
                return []      # one unreadable alternative makes the whole unknown
            out.extend(got)
        return out
    return [([y], mo, d) for y, mo, d in readings(s)]


def parse_hit(s):
    got = parse_hits(s)
    return got[0] if len(got) == 1 else None


def placeholder(d):
    """A system default date of birth (1900-01-01, 1970-01-01, 1911-11-11 or any
    year before 1900) is unknown, never a fact."""
    if not d:
        return False
    y, m, dd = d
    if y < 1900:
        return True
    if (m, dd) == (1, 1) and y in (1900, 1901, 1970):
        return True
    return (y, m, dd) == (1911, 11, 11)
