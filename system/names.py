"""Name comparison, principle 8."""
import re
import unicodedata

PLACEHOLDERS = {"na", "n/a", "test", "unknown", "xxx", "none", "null", "nil",
                "tbd", "tba", "nn", "noname", "dummy", "sample", "x", "xx",
                "xxxx", "unk", "anon", "anonymous", "customer", "user", "fnu", "lnu"}


def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    repl = {"ß": "ss", "ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae", "đ": "d",
            "Đ": "d", "ł": "l", "Ł": "l", "ı": "i", "œ": "oe", "þ": "th"}
    return "".join(repl.get(c, c) for c in s).lower()


def raw_parts(name):
    """Lowercase parts with brackets, accents and punctuation removed, in order."""
    s = fold(name)
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]|\{[^}]*\}", " ", s)
    s = re.sub(r"['’`´]", "", s)
    s = re.sub(r"[^\w\s/]|_", " ", s)
    return [p for p in s.split() if p]


class Namer:
    def __init__(self, groups, forms):
        self.group = {}
        for i, g in enumerate(groups):
            for p in g:
                for q in raw_parts(p):
                    self.group.setdefault(q, set()).add(i)
        self.forms = set()
        for f in forms:
            self.forms.update(raw_parts(f))

    def parts(self, name, company=False):
        """Distinct real parts in order: no initials, no placeholders, no digits,
        and for companies no legal forms."""
        out = []
        for p in raw_parts(name):
            if "/" in p:
                if p in PLACEHOLDERS:
                    continue
                p = p.replace("/", "")
            # principle 8: digits are placeholders, but a part such as N26 is a name
            if len(p) < 2 or p in PLACEHOLDERS or p.isdigit():
                continue
            if company and p in self.forms:
                continue
            if p not in out:
                out.append(p)
        return out

    def part_match(self, a, b):
        if a == b:
            return True
        ga, gb = self.group.get(a), self.group.get(b)
        if ga and gb and ga & gb:
            return True
        n = min(len(a), len(b))
        if n < 4:
            return False
        limit = 1 if n <= 6 else 2
        if abs(len(a) - len(b)) > limit:
            return False
        return edits(a, b, limit) <= limit

    def units(self, parts):
        """Single parts plus neighbours written together: Abdul Salam as Abdulsalam,
        either order since listed names often put the surname first, and runs of
        three such as Abd al Rahman."""
        u = [((i,), p) for i, p in enumerate(parts)]
        for i in range(len(parts) - 1):
            u.append(((i, i + 1), parts[i] + parts[i + 1]))
        for i in range(len(parts) - 2):
            u.append(((i, i + 1, i + 2), parts[i] + parts[i + 1] + parts[i + 2]))
        return u

    def matches(self, pa, pb):
        """Over every one to one assignment of matching parts (a joined match counts
        once), the most matches, the most parts of pa covered and the most parts of
        pb covered, each maximised on its own so the result does not depend on
        which name comes first."""
        if not pa or not pb:
            return 0, 0, 0
        ua, ub = self.units(pa), self.units(pb)
        pairs = []
        for ia, sa in ua:
            for ib, sb in ub:
                if len(ia) > 1 and len(ib) > 1:
                    continue
                # principle 8: a joined form matches when written the same; the
                # edit allowance applies to single parts only
                joined = len(ia) > 1 or len(ib) > 1
                if (sa == sb) if joined else self.part_match(sa, sb):
                    pairs.append((frozenset(ia), frozenset(ib)))
        pairs = sorted(set(pairs), key=lambda x: (sorted(x[0]), sorted(x[1])))
        best = [0, 0, 0]
        seen = set()

        def search(k, used_a, used_b, cnt):
            key = (k, used_a, used_b)
            if key in seen:
                return
            seen.add(key)
            best[0] = max(best[0], cnt)
            best[1] = max(best[1], len(used_a))
            best[2] = max(best[2], len(used_b))
            for j in range(k, len(pairs)):
                ia, ib = pairs[j]
                if not (ia & used_a) and not (ib & used_b):
                    search(j + 1, used_a | ia, used_b | ib, cnt + 1)

        search(0, frozenset(), frozenset(), 0)
        return tuple(best)

    def agree(self, a, b, company=False):
        """Names agree: two parts match, or every part of the shorter name matches
        under some assignment. A "Surname, Given" name is also tried in written
        order, so joined forms follow the order people write them."""
        for x in orders(a):
            for y in orders(b):
                if self._agree(x, y, company):
                    return True
        return False

    def _agree(self, a, b, company=False):
        pa, pb = self.parts(a, company), self.parts(b, company)
        if not pa or not pb:
            return False
        cnt, ca, cb = self.matches(pa, pb)
        if cnt >= 2:
            return True
        if cnt < 1:
            return False
        if len(pa) <= len(pb) and ca == len(pa):
            return True
        return len(pb) <= len(pa) and cb == len(pb)

    def compare(self, a, b, company=False):
        """True when the names agree, False when they disagree, None when they
        cannot be compared because they share no script. A name written only in
        another script is unknown, never a mismatch."""
        if self.agree(a, b, company):
            return True
        if not self.parts(a, company) or not self.parts(b, company):
            return None   # nothing left to compare, such as a bare legal form
        sa, sb = scripts(a), scripts(b)
        if not sa or not sb or not (sa & sb):
            return None
        return False

    def real(self, name, company=False):
        return len(self.parts(name, company))


def orders(name):
    """The name as given, and for "Surname, Given" also "Given Surname"."""
    out = [name or ""]
    if name and name.count(",") == 1:
        last, first = name.split(",")
        if first.strip() and last.strip():
            out.append(first.strip() + " " + last.strip())
    return out


def scripts(name):
    """Writing systems of the letters in a name (LATIN, CYRILLIC, ARABIC, CJK...)."""
    out = set()
    for c in fold(name):
        if c.isalpha():
            try:
                out.add(unicodedata.name(c).split()[0])
            except ValueError:
                out.add("OTHER")
    return out


def edits(a, b, limit=99):
    """Levenshtein distance; a swap of two letters counts as two edits."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        low = i
        for j, cb in enumerate(b, 1):
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            cur.append(v)
            low = min(low, v)
        if low > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def query_key(name):
    """Search results are filed by the name's lowercase words in alphabetical order."""
    return " ".join(sorted(raw_parts(name)))


def query_key_parts(name):
    """The key as the provider files it: apostrophes split words and single
    letters are dropped ("Thomas P. Walsh" under "thomas walsh", "O'Connor,
    Michael" under "connor michael")."""
    s = re.sub(r"['\u2019`\u00b4]", " ", name or "")
    return " ".join(sorted(p for p in raw_parts(s) if len(p) >= 2))


def query_key_dropped(name):
    """Same key when the provider drops letters it cannot write (Paweł as pawe)."""
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = "".join(c for c in s if ord(c) < 128)
    return " ".join(sorted(raw_parts(s)))
