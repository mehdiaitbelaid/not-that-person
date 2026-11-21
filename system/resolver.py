"""Find who the customer is (principles 2 and 3). Indexes are built once."""
import re

import countries
import dates
from facts import DOC_NUM, Person, is_company, note_check
from loader import field
from names import fold, orders, query_key, query_key_dropped, query_key_parts, raw_parts


def deletes(word, k):
    """Every string made by removing up to k letters."""
    out, layer = {word}, {word}
    for _ in range(k):
        layer = {w[:i] + w[i + 1:] for w in layer for i in range(len(w))}
        out |= layer
    return out


def digits(s):
    return re.sub(r"\D", "", s or "")


class DB:
    def __init__(self, data, namer):
        self.namer = namer
        self.customers = {}
        for r in data["customers"]:
            rid = field(r, "record_id", "customer_id", "id")
            if rid and rid not in self.customers:
                self.customers[rid] = r
        self.acc_by_id, self.acc_by_login, self.acc_by_cus = {}, {}, {}
        for a in data["accounts"]:
            cid = field(a, "customer_id")
            self.acc_by_id.setdefault(field(a, "account_id"), []).append(cid)
            lh = field(a, "login_handle").lower()
            if lh:
                self.acc_by_login.setdefault(lh, []).append(cid)
            self.acc_by_cus.setdefault(cid, set()).add(field(a, "account_id"))
        self.app_by_cus, self.cus_by_app = {}, {}
        for o in data["onboarding"]:
            cid, app = field(o, "customer_id"), field(o, "kyc_applicant_id", "applicant_id")
            if not app:
                continue
            if not cid:
                continue
            self.app_by_cus.setdefault(cid, set()).add(app)
            self.cus_by_app.setdefault(app, set()).add(cid)
        self.kyc_by_app = {}
        for k in data["kyc_checks"]:
            self.kyc_by_app.setdefault(field(k, "applicant_id"), []).append(k)
        self.notes_by_email = {}
        for n in data["notes"]:
            e = field(n, "requester_email", "email").lower()
            if e:
                self.notes_by_email.setdefault(e, []).append(n)
        for v in self.notes_by_email.values():
            v.sort(key=lambda n: field(n, "note_id"))
        self.sr = {}
        for r in data["search_results"]:
            self.sr.setdefault(query_key(field(r, "query")), []).append(r)
        for v in self.sr.values():
            v.sort(key=lambda r: field(r, "result_id"))
        self.by_email, self.by_login_name, self.by_token = {}, {}, {}
        for rid in sorted(self.customers):
            r = self.customers[rid]
            e = field(r, "email").lower()
            if e:
                self.by_email.setdefault(e, []).append(rid)
            ln = field(r, "login_name").lower()
            if ln:
                self.by_login_name.setdefault(ln, []).append(rid)
            for f in ("full_name", "preferred_name", "login_name"):
                for t in self.tokens(field(r, f), joined=True):
                    self.by_token.setdefault(t, set()).add(rid)
        # deletion index over every name part, so retrieval finds every part
        # within principle 8's edit limits, not only exact or listed forms
        self.by_delete = {}
        for t in sorted(self.by_token):
            if t.startswith("#") or len(t) < 4:
                continue
            for v in deletes(t, 1 if len(t) <= 6 else 2):
                self.by_delete.setdefault(v, set()).add(t)
        self.notes = data["notes"]
        self._union()

    def tokens(self, name, joined=False):
        out = set()
        for form in orders(name):
            out |= self._tokens(form, joined)
        return out

    def norm_parts(self, name):
        """The comparator's own parts (placeholders, initials and, for companies,
        legal forms removed), as both a person's and a company's name."""
        out = []
        for company in (False, True):
            ps = self.namer.parts(name, company)
            if ps not in out:
                out.append(ps)
        return out

    def _tokens(self, name, joined=False):
        out = set()
        for parts in self.norm_parts(name):
            out |= self._unit_tokens(parts, joined)
        return out

    def _unit_tokens(self, parts, joined):
        out = set()
        for p in parts:
            out.add(p)
            for g in sorted(self.namer.group.get(p, ())):
                out.add("#%d" % g)
        if joined:
            for i in range(len(parts) - 1):
                out.add(parts[i] + parts[i + 1])
            for i in range(len(parts) - 2):
                out.add(parts[i] + parts[i + 1] + parts[i + 2])
        return out

    def near(self, part):
        """Indexed name parts that could match `part` under principle 8."""
        out = {part} if part in self.by_token else set()
        if len(part) < 4:
            return out
        for v in deletes(part, 2):
            for t in self.by_delete.get(v, ()):
                if self.namer.part_match(part, t):
                    out.add(t)
        return out

    def applicants_of(self, cid):
        return sorted(self.app_by_cus.get(cid, ()))

    def search_for(self, name):
        out, seen = [], set()
        for k in (query_key(name), query_key_dropped(name), query_key_parts(name)):
            for r in self.sr.get(k, []):
                rid = field(r, "result_id")
                if rid not in seen:
                    seen.add(rid)
                    out.append(r)
        return sorted(out, key=lambda r: field(r, "result_id"))

    def _union(self):
        """Principle 3: same phone and same full date of birth, or the same document
        number on approved checks, make one person; links are followed transitively."""
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def join(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                if ra < rb:
                    parent[rb] = ra
                else:
                    parent[ra] = rb

        first = {}
        for rid in sorted(self.customers):
            r = self.customers[rid]
            ph = digits(field(r, "phone"))
            d = dates.parse(field(r, "dob"))
            # principle 3 merges on any full date; placeholder dates are judged only
            # when a date is used to clear or confirm
            if len(ph) >= 6 and dates.full(d):
                k = (ph, d)
                if k in first:
                    join(first[k], rid)
                else:
                    first[k] = rid
        doc_first = {}
        for app in sorted(self.kyc_by_app):
            for k in self.kyc_by_app[app]:
                if field(k, "result").lower() != "approved":
                    continue
                num = re.sub(r"[\s\-]", "", field(k, "document_number")).upper()
                if len(num) < 4:
                    continue
                for cid in sorted(self.cus_by_app.get(app, ())):
                    if cid not in self.customers:
                        continue
                    if num in doc_first:
                        join(doc_first[num], cid)
                    else:
                        doc_first[num] = cid
        # approved checks recorded only in notes carry document numbers too
        for n in self.notes:
            t = field(n, "text")
            if not DOC_NUM.search(t):
                continue
            c = note_check(n)
            if not c or not c.approved or len(c.doc) < 5:
                continue
            for cid in self.by_email.get(field(n, "requester_email").lower(), []):
                num = c.doc.upper()
                if num in doc_first:
                    join(doc_first[num], cid)
                else:
                    doc_first[num] = cid
        self.members = {}
        for rid in sorted(self.customers):
            self.members.setdefault(find(rid), []).append(rid)
        self.root = {rid: find(rid) for rid in self.customers}

    def person_ids(self, rid):
        return self.members.get(self.root.get(rid, rid), [rid])

    # principle 2: the records that fit the screened details
    def fits(self, rid, alert, use_name=True):
        r = self.customers[rid]
        company = is_company(field(alert, "entity_type"))
        sname = field(alert, "customer_name", "name")
        if use_name and sname:
            names = [field(r, f) for f in ("full_name", "preferred_name", "login_name")]
            if not any(n and self.namer.agree(n, sname, company) for n in names):
                return False
        # every reading of either date counts: a screened date that could be read
        # two ways never eliminates a record that fits one of them
        sraw, rraw = field(alert, "dob"), field(r, "dob")
        sds = dates.readings(sraw) if dates.ambiguous(sraw) else [d for d in [dates.parse(sraw)] if d]
        rds = dates.readings(rraw) if dates.ambiguous(rraw) else [d for d in [dates.parse(rraw)] if d]
        if sds and rds and not any(dates.compatible(x, y) for x in sds for y in rds):
            return False
        sc = countries.norm(field(alert, "country"))
        if sc:
            rc = {countries.norm(field(r, f)) for f in ("residence_country", "nationality")}
            rc.discard(None)
            if rc and sc not in rc:
                return False
        city = fold(field(alert, "city")).strip()
        if city:
            where = fold(field(r, "city") + " " + field(r, "address"))
            if where.strip() and city not in where:
                return False
        return True

    def linked(self, alert):
        """Record ids the alert's own link leads to, and a label for the path."""
        ids, how = set(), []
        acc = field(alert, "account_ref", "account_id")
        if acc and acc in self.acc_by_id:
            ids.update(x for x in self.acc_by_id[acc] if x)
            how.append("account")
        lh = field(alert, "login_handle").lower()
        if lh:
            if lh in self.acc_by_login:
                ids.update(x for x in self.acc_by_login[lh] if x)
                how.append("login")
            elif lh in self.by_login_name:
                ids.update(self.by_login_name[lh])
                how.append("login")
        em = field(alert, "email").lower()
        if em and em in self.by_email:
            ids.update(self.by_email[em])
            how.append("email")
        ids = {i for i in ids if i in self.customers}
        return sorted(ids), how

    def search(self, alert):
        sname = field(alert, "customer_name", "name")
        cand = set()
        # the same parts and joins the comparator uses, so anything it would accept
        # can be retrieved
        for t in self.tokens(sname, joined=True):
            cand |= self.by_token.get(t, set())
        units = set()
        for form in orders(sname):
            for parts in self.norm_parts(form):
                units.update(parts)
                units.update(parts[i] + parts[i + 1] for i in range(len(parts) - 1))
                units.update(parts[i] + parts[i + 1] + parts[i + 2] for i in range(len(parts) - 2))
            parts = [p for p in raw_parts(form) if len(p) >= 2]
            units.update(parts)
            units.update(parts[i] + parts[i + 1] for i in range(len(parts) - 1))
            units.update(parts[i] + parts[i + 1] + parts[i + 2] for i in range(len(parts) - 2))
        for p in sorted(units):
            for t in sorted(self.near(p)):
                cand |= self.by_token.get(t, set())
        return sorted(r for r in cand if self.fits(r, alert))

    def resolve(self, alert):
        """Return (list of Person, how). Each Person is one real customer."""
        ids, how = self.linked(alert)
        if ids:
            if len({self.root[i] for i in ids}) > 1:
                pick = [i for i in ids if self.fits(i, alert)]
                if not pick:
                    pick = [i for i in ids if self.fits(i, alert, use_name=False)]
                ids = pick or ids
        else:
            ids = self.search(alert)
            how = ["search"] if ids else []
        groups = {}
        for i in ids:
            groups.setdefault(self.root[i], []).append(i)
        people = []
        for root in sorted(groups):
            p = Person(self.person_ids(root), self)
            p.primary = sorted(groups[root])[0]
            people.append(p)
        return people, how
