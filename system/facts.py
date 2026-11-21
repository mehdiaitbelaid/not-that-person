"""Gather facts for both sides: the customer as one person (principles 3 and 4)
and the listed profile (principle 5)."""
import re

import countries
import dates
from loader import field, multi
from names import raw_parts

APPROVED = {"approved", "passed", "pass", "verified", "clear", "cleared", "success",
            "successful", "accepted", "ok", "valid"}
DOC_WORDS = r"passport|driving licen[cs]e|driver'?s licen[cs]e|national id|id card|identity card|identity document|residence permit|residence card|identification|travel document|\bid\b"
# principle 4: only explicit approval counts, and any negative or pending word wins
GOOD = r"\b(?:verified|verifies|approved|approval|pass|passed|cleared|validated|confirmed|successful(?:ly)?|succeeded|accepted|authenticated|match(?:es|ed)?|completed?|finalized|finalised)\b"
BAD = r"\b(?:not|never|no longer)\b[^.;]{0,30}?\b(?:verified|approved|accepted|validated|successful|passed|cleared|confirmed|completed?|valid)\b|\bunsuccessful\w*|\bfail\w*|\breject\w*|\bdeclin\w*|\bpending\b|\bawait\w*|\bunder review\b|\bfor review\b|\bin review\b|\bon hold\b|\bcould ?n[o']t\b|\bunable\b|\bdenied\b|\brefus\w*|\bexpir\w*|\binvalid\w*|\bmismatch\w*|\blapsed\b|\bvoid\w*|\brevoked\b|\bfraud\w*|\bforged\b|\bincomplete\b|\bsuspend\w*|\bescalat\w*|\bflagged\b|\bretry\b|\bresubmi\w*"
DOB_CUE = r"born|dob|d\.o\.b\.?|date of birth|birth ?date|birthdate|birth on"
PERSON_TYPES = {"individual", "person", "natural person", "private individual", "private person",
                "individual customer", "retail"}
COMPANY_TYPES = {"company", "organisation", "organization", "entity", "business", "corporate",
                 "legal entity", "corporation", "firm", "legal person", "partnership", "trust"}


def kind(v):
    """True for a company, False for a person, None when missing or unrecognised."""
    k = re.sub(r"[^a-z ]", " ", (v or "").lower()).strip()
    k = re.sub(r"\s+", " ", k)
    if k in COMPANY_TYPES:
        return True
    if k in PERSON_TYPES:
        return False
    return None


def is_company(v):
    return kind(v) is True


def ident(v):
    """Identifier compared without spaces, punctuation or case."""
    return re.sub(r"[^0-9a-z]", "", (v or "").lower())


class Check:
    """One identity check, from the KYC provider or written up in a note."""

    def __init__(self, cid, when, name, dob, country, approved, kind, raw=""):
        self.id, self.when, self.name = cid, when, name
        self.dob = None if dates.placeholder(dob) else dob
        self.doc = ""
        self.raw = raw
        self.completed = False
        self.third_party = False
        self.country, self.approved, self.kind = country, approved, kind
        # a note that names a date of birth or a holder we could not bind leaves
        # that fact unknown rather than falling back to an older check
        self.dob_unread = False
        self.name_unread = False

    time = None

    def order(self):
        # full timestamp precision: date, then time of day when known, then id
        return (dates.earliest(self.when) if self.when else (0, 0, 0),
                self.time if self.time else (-1, -1, -1), self.id)

    def identity(self):
        return ((self.name or "").upper(), self.dob)


def clock(raw):
    m = re.search(r"[T ](\d{1,2}):(\d{2})(?::(\d{2}))?", raw or "")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)) if m else None


STOP = {"ID", "DOB", "KYC", "UK", "US", "USA", "UAE", "DL", "PEP", "AML", "OK", "ID:", "N/A"}
# words that make a capitalised run a heading or a label, never a person
NONNAME = {"CHECK", "CHECKS", "DOCUMENT", "DOCUMENTS", "COMPLETED", "COMPLETE", "FINALIZED",
           "FINALISED", "VERIFIED", "APPROVED", "PASSED", "PASS", "CLEARED", "IDENTITY",
           "VERIFICATION", "KYC", "RESULT", "RESULTS", "STATUS", "PASSPORT", "LICENCE", "LICENSE",
           "ID", "NOTE", "NOTES", "ONFIDO", "SUMSUB", "VERIFF", "PERSONA", "JUMIO", "DOB", "OK",
           "SUCCESS", "SUCCESSFUL", "REVIEW", "PENDING", "FAILED", "REJECTED", "NATIONAL",
           "DRIVING", "CARD", "DONE", "CONFIRMED", "VALIDATED", "ACCEPTED", "UPDATE", "SUMMARY",
           "APPLICANT", "CUSTOMER", "HOLDER", "NAME", "DATE", "BIRTH", "ISSUED", "EXPIRY",
           "PROVIDER", "OUTCOME", "REPORT", "FINAL", "MATCH", "MATCHED", "AND", "THE", "OF", "FOR",
           "ALERT", "SCREENING", "ACCOUNT", "TEAM", "ONBOARDING", "COMPLIANCE", "AUTHENTICATED"}
NEG = (r"\bnot\b|n['’]t\b|\bno\b(?!\.?\s*[:#]?\s*[a-z0-9]*\d)|\bnever\b|\bnone\b|\bnothing\b|\bneither\b|\bnor\b|\bwithout\b|\bfail\w*|\bunsuccess\w*"
       r"|\breject\w*|\bdeclin\w*|\bpending\b|\bawait\w*|\bincomplete\b|\bunable\b|\bexpir\w*"
       r"|\binvalid\w*|\bdenied\b|\brefus\w*|\brevoked\b|\bsuspend\w*|\b(?:under|for|in|pending|awaiting|manual) review\b|\bon hold\b"
       r"|\bmismatch\w*|\bfraud\w*|\bforged\b|\bvoid\w*|\blapsed\b|\bescalat\w*|\bflagged\b"
       r"|\bretry\b|\bresubmi\w*|\bcancel\w*|\bwithdrawn\b|\bunverified\b")
LABEL_BEFORE = (r"(?:\blegal name|\bfor|\bholder as|\bas holder|\bholder|\bname\s*:?|\bname on (?:the )?document\s*:?|\bin the name of"
                r"|\bbelong(?:ing|s) to|\bheld by|\bissued to)\s*:?\s*$")
BINDER_BEFORE = (r"(?:\bfor|\bholder as|\bas holder|\bholder|\bname\s*:?|\bname on (?:the )?document\s*:?|\bin the name of|\bof"
                 r"|\bbelong(?:ing|s) to|\bheld by|\bissued to|\bmatched|\bsubmitted by|\bpresented by"
                 r"|\bprovided by|\bused by|\bshows?|\bsuccessful\s*:|\bpassed\s*:|\bapproved\s*:"
                 r"|\bcheck on|\bverification on|\bthat|\bverifies|\bconfirms|\bvalidates|\blegal name"
                 r"|\bverified|\bvalidated|\bcleared|\bapproved|\bauthenticated|\bconfirmed|\bvetted"
                 r"|\bmatches|\bshows|\bidentity of)\s*:?\s*$")
BINDER_AFTER = (r"^\s*(?:['’]s\b|\(|,\s*(?:born|dob|date of birth|whose|with|who)\b|\s+(?:born|dob)\b"
                r"|,?\s+(?:was|is|has|have|had|passed|successfully|provided|presented|submitted|underwent"
                r"|completed|cleared|holds|using|from|confirmed|vetted|verified|identity|id check|check)\b)")


def note_sentences(t):
    """Sentences of a note; abbreviations that end in a dot are kept whole."""
    t = re.sub(r"(?i)\bd\.o\.b\.?", "DOB", t or "")
    t = re.sub(r"(?i)\bno\.\s*(?=[:#]?\s*\w*\d)", "No ", t)
    return [x.strip() for x in re.split(r"(?<=[.!?;])\s+(?=[A-Z(\[])|\n+", t) if x.strip()]


def caps_runs(t):
    """Runs of words written in capitals, with their start and end offsets."""
    runs = []
    for m in re.finditer(r"(?:(?<=\s)|^|(?<=[(\[:]))([^\W\d_][^\W\d_'’.\-]*(?:[-'’][^\W\d_]{2,})*)", t):
        w = m.group(1)
        if w.isupper() and len(w) >= 2 and w not in STOP:
            if runs and t[runs[-1][1]:m.start(1)].strip() == "":
                runs[-1] = (runs[-1][0], m.end(1))
            else:
                runs.append((m.start(1), m.end(1)))
    return [(a, b, t[a:b]) for a, b in runs if len(t[a:b].split()) >= 2]


def name_like(run):
    words = [w.strip(".,'") for w in run.split()]
    return len(words) >= 2 and not any(w.upper() in NONNAME for w in words)


ANY_HOLDER = re.compile(
    r"(?:\bfor|\bholder(?: as)?|\bname(?: on (?:the )?document)?\s*:|\bconcluded\s*:|\bverified\s*:"
    r"|\bcompleted\s*:|\bin the name of|\b(?:passport|licen[cs]e|id|card|document|identity) of)\s+([^\W\d_][\w'\-]*(?:\s+[^\W\d_][\w'\-]*){1,3}?)"
    r"(?=\s*(?:\(|,|\.|;|$))", re.I)


THIRD_PARTY = set()   # sentences whose named document holder is someone else


def any_case_holders(sent):
    """Holders written in any letter case after an explicit label: "for john
    smith (DOB ...)", "concluded: John Smith", "Name on document: John Smith"."""
    out = []
    for m in ANY_HOLDER.finditer(sent):
        n = m.group(1).strip()
        tail = sent[m.end(1):m.end(1) + 40].lower()
        # "Ruth Baxter, the customer's mother": a third party, not the holder
        if re.match(r"\s*,?\s*(?:the\s+)?(?:customer|client|applicant)['\u2019]s\b", tail) or \
                re.match(r"\s*,?\s*(?:his|her|their|the)\s+" + RELATION, tail):
            THIRD_PARTY.add(sent)
            continue
        if name_like(n.upper()) and not countries.mentioned(n) and n not in out:
            out.append(n)
    return out


def label_names(sent):
    """Names a sentence gives under an explicit label (name on document, holder,
    belonging to): valid anywhere in an approved note."""
    out = []
    for a, b, run in caps_runs(sent):
        if name_like(run) and re.search(LABEL_BEFORE, sent[max(0, a - 30):a].lower()):
            out.append(run)
    return out


def bound_names(sent):
    """Holder names a sentence binds explicitly: after for, holder, name:, of or an
    approval verb, or as the sentence's subject before a possessive, a bracket, a
    birth cue or a verb. Headings and labels never qualify."""
    out = []
    lead = re.match(r"\s*(?:on\s+[^,]{4,30},\s*)?", sent, re.I).end()
    for a, b, run in caps_runs(sent):
        if not name_like(run):
            continue
        before = sent[max(0, a - 30):a].lower()
        after = sent[b:b + 30].lower()
        if re.match(r"\s*,?\s*(?:the\s+)?(?:customer|client|applicant|holder|account holder)['\u2019]s\b", after) \
                or re.match(r"\s*,?\s*(?:his|her|their|the)\s+" + RELATION, after):
            THIRD_PARTY.add(sent)
            continue
        start = a <= lead + 1 or re.search(r",\s*$", sent[max(0, a - 3):a])
        if re.search(BINDER_BEFORE, before) or (start and re.match(BINDER_AFTER, after)):
            if run.upper() not in [x.upper() for x in out]:
                out.append(run)
    if not out:
        for m in re.finditer(r"(?:\bname on (?:the )?document\s*:|\bholder\s*:?|\bname\s*:|\bin the name of|\bfor)\s+([A-Z][\w'\-]+(?:\s+[A-Z][\w'\-]+)+)", sent):
            n = m.group(1)
            if name_like(n.upper()) and not countries.mentioned(n) and n not in out:
                out.append(n)
    return out


BAD_GAP = r"\b(?:issued?|expir\w*|valid|until|unavailable|unknown|not|missing|withheld|redacted|checked|processed|submitted|reviewed|created|dated)\b"


def bound_dob(t):
    """The date of birth a sentence states: a date after a birth cue in the same
    clause, a date right before one ("her 08/10/2000 date of birth"), or a date in
    brackets right after the holder's name. Returns (date, raw, cue seen)."""
    low = t.lower()
    found = dates.find_all(t)
    cue_seen = bool(re.search(r"\b(?:" + DOB_CUE + r")", low))
    # a date written right before the cue ("whose 1986-12-10 date of birth") is
    # tried first, since a date after the cue may be the check's own date
    for a, b, d in found:
        if re.match(r"\s*(?:as\s+(?:the\s+|her\s+|his\s+|their\s+)?)?(?:" + DOB_CUE + r")\b", low[b:]):
            return d, t[a:b], True
    for m in re.finditer(r"\b(?:" + DOB_CUE + r")", low):
        for a, b, d in found:
            if a < m.end():
                continue
            gap = low[m.end():a]
            if len(gap) > 30 or re.search(r"[.;\n]", gap) or re.search(BAD_GAP, gap):
                break
            return d, t[a:b], True
    for a, b, run in caps_runs(t):
        m = re.match(r"\s*\(\s*", t[b:])
        if m:
            for x, y, d in found:
                if x == b + m.end() and re.match(r"\s*\)", t[y:]):
                    return d, t[x:y], True
    return None, "", cue_seen


EVENT_CUE = r"(?:\bon|\bas of|\bdated|\bat|\bcompleted|\bchecked|\bverified|\bapproved|\bcleared)\s*:?\s*$"


def unclear_check(note):
    """A note that reads like an identity check but gives no result we can read."""
    t = field(note, "text", "body", "note").lower()
    return bool(re.search(DOC_WORDS, t) and re.search(DOB_CUE + r"|identity|check|verif|kyc", t))


DOC_NUM = re.compile(r"(?:passport|licen[cs]e|document|id|card)\s*(?:number|no\.?|num|#)\s*[:#]?\s*([A-Z0-9][A-Z0-9\-]{4,})", re.I)


# an approval must be completed and affirmative: future, conditional or
# hypothetical wording in the sentence means it has not happened
MODAL = (r"\bwill\b|\bwould\b|\bshall\b|\bto be\b|\bif\b|\bonce\b|\bwhen (?:the |it |they |we )?(?:is|are|has|have|gets?|arrives?|completes?)\b"
         r"|\bpending\b|\bscheduled\b|\btomorrow\b|\bexpected\b|\bshould\b|\bmay\b(?!\s+\d)|\bmight\b|\bcan be\b"
         r"|\bgoing to\b|\bupon (?:receipt of|completion of) (?:the |any )?(?:missing|outstanding|further|additional)\b"
         r"|\bunless\b|\bprovided that\b|\bassuming\b|\bplanned\b|\bnext (?:week|month|day)\b"
         r"|\bsubject to\b|\bnearly\b|\balmost\b|\bpartially\b|\bpartly\b")


# markers that mean the outcome is still open, as opposed to a plain refusal
PENDING = (r"\bpending\b|\bawait\w*|\b(?:under|for|in|pending|awaiting|manual) review\b|\bon hold\b"
           r"|\bincomplete\b|\bescalat\w*|\bflagged\b|\bretry\b|\bresubmi\w*|\bsuspend\w*")


# an explicit rejection or expiry of the check itself
REJECT = (r"\b(?:rejected|declined|failed|refused|expired|denied|revoked|cancell?ed|withdrawn)\b"
          r"|\b(?:was|were|is|has|have|had)\s+not\s+(?:been\s+)?(?:verified|approved|accepted|validated|confirmed|cleared|passed|succeeded)\b"
          r"|\bcould\s*n[o']t\s+(?:be\s+)?(?:verified|approved|validated|confirmed|cleared)\b|\bunable to (?:verify|validate|confirm|approve)\b"
          r"|\bnone of (?:the|those|these) details (?:was|were) verified\b|\bno approval (?:was|has been) (?:issued|given|granted)\b"
          r"|\bnot successful\b|\bunsuccessful\b|\bremains? unverified\b|\bverification failed\b")


ID_TERM = (r"\b(?:check|checks|verification|verified|verify|identity|id|passport|licen[cs]e|document"
           r"|kyc|onboarding|applicant|submission|submitted)\b")


def rejected(t):
    """An unmistakable rejection: a rejection or expiry predicate in a sentence
    about the identity check (a declined payment or login does not count), and no
    approval or completion word in any sentence once those phrases are set aside."""
    low = t.lower()
    if not any(re.search(REJECT, x.lower()) and re.search(ID_TERM, x.lower()) for x in note_sentences(t)):
        return False
    if re.search(COMPLETION_ANY, low):
        return False
    rest = re.sub(REJECT, " ", low)
    # "carries no current approval": an approval word under a negation is part of
    # the refusal, not an approval
    rest = re.sub(r"\b(?:no|not|never|without)\b(?:\s+[a-z]+){0,2}?\s+" + GOOD, " ", rest)
    return not re.search(GOOD, rest)


def classify(t):
    """(approval sentences, other sentences that bear on the check) of a note.
    A sentence approves only when it has an approval word and no negative,
    pending, future or conditional marker."""
    appr, neg = [], []
    for s in note_sentences(t):
        low = s.lower()
        if re.search(NEG, low) or (re.search(GOOD, low) and re.search(MODAL, low)):
            neg.append(s)
        elif re.search(GOOD, low):
            appr.append(s)
    return appr, neg


def loose_facts(note):
    """Names and birth dates written in an identity note whose result we cannot
    read. They are not verified facts, but they may be the customer's, so they
    keep a location difference from clearing a name and DOB agreement."""
    t = field(note, "text", "body", "note")
    names = [run for _, _, run in caps_runs(t) if name_like(run)]
    for sent in note_sentences(t):
        for n in bound_names(sent) + label_names(sent) + any_case_holders(sent):
            if n not in names:
                names.append(n)
    dobs = []
    for s in note_sentences(t):
        d, raw, _ = bound_dob(s)
        if d:
            dobs.extend(dates.readings(raw) if dates.ambiguous(raw) else [d])
    return names, dobs


COMPLETION = r"\b(?:concluded|processed)\b"
COMPLETION_ANY = r"\b(?:concluded|processed|completed?|finali[sz]ed)\b"


def completion_check(note, t):
    """A note that only says a check concluded or was processed, with no approval,
    negative, pending, future or conditional word. Its holder and birth date may
    support a confirmation but never a clearance."""
    low = t.lower()
    if not re.search(COMPLETION, low) or re.search(NEG, low) or re.search(MODAL, low) \
            or re.search(PENDING, low):
        return None
    sents = [x for x in note_sentences(t) if re.search(COMPLETION, x.lower())]
    names = []
    for x in sents:
        for n in bound_names(x) + any_case_holders(x):
            if n.upper() not in [y.upper() for y in names]:
                names.append(n)
    dob, raw = None, ""
    for x in note_sentences(t):
        if re.search(RELATION, x, re.I):
            continue
        d, r, _ = bound_dob(x)
        if d:
            dob, raw = d, r
            break
    if len(names) != 1 or not dob:
        return None
    created = dates.parse(field(note, "created_at", "date"))
    c = Check(field(note, "note_id", "id"), created, names[0], dob, None, False, "note", raw)
    c.completed = True
    c.open = False
    return c


def note_check(note):
    """Read an identity check written up in a note, sentence by sentence.
    Approved only when some sentence states approval and no sentence carries a
    negative or pending marker; a note with both is returned as unclear (None).
    The holder comes only from an explicit binding in an approval sentence."""
    t = field(note, "text", "body", "note")
    if not t or not re.search(DOC_WORDS, t.lower()):
        return None
    appr, neg = classify(t)
    if not appr and not neg:
        return completion_check(note, t)
    if appr and neg:
        return None          # mixed polarity: unclear, caught by unclear_check
    if neg and not rejected(t):
        # negative or open wording without an unmistakable rejection of the
        # check itself ("approved ... without issues"): unclear, never rejected
        return None
    created = dates.parse(field(note, "created_at", "date"))
    approved = bool(appr)
    # a note with no approval is either a plain refusal (rejected, expired,
    # failed: not evidence, principle 4) or still open (pending, future)
    still_open = not approved and any(re.search(PENDING, x.lower()) or re.search(MODAL, x.lower()) for x in neg)
    sents = appr if approved else neg
    names = []
    found = [n for x in sents for n in bound_names(x)]
    if approved:
        found += [n for x in note_sentences(t) for n in label_names(x)]
        # holders written in mixed or lower case after an explicit binder
        found += [n for x in sents for n in any_case_holders(x)]
    for n in found:
        if n.upper() not in [x.upper() for x in names]:
            names.append(n)
    name = names[0] if len(names) == 1 else ""
    dob, raw, cue = None, "", False
    for s in note_sentences(t):
        if re.search(RELATION, s, re.I) or (approved and s in neg):
            continue
        d, r, c = bound_dob(s)
        cue = cue or c
        if d:
            dob, raw = d, r
            break
    when = None
    for s in sents:
        for a, b, d in dates.find_all(s):
            if d == dob and s[a:b] == raw:
                continue
            if dates.full(d) and (re.search(EVENT_CUE, s[max(0, a - 14):a].lower())
                                  or re.search(r"\(\s*[A-Z][\w ]*,\s*$", s[max(0, a - 25):a])):
                when = d
                break
        if when:
            break
    when = when or created
    # a birth date equal to the check or note date, or one that makes the holder
    # younger than ten when the note was written, is a misread
    if dob and (dob in (when, created) or (created and dates.max_age(dob, created) < 10)):
        dob, raw, cue = None, "", True
    found_c = sorted(countries.mentioned(re.sub(r"\([^)]*\)", " ", t))) or sorted(countries.mentioned(t))
    country = found_c[0] if len(found_c) == 1 else None
    c = Check(field(note, "note_id", "id"), when, name, dob, country, approved, "note", raw)
    c.open = still_open
    c.dob_unread = dob is None and cue
    c.name_unread = not name
    c.third_party = any(x in THIRD_PARTY for x in note_sentences(t))
    m = DOC_NUM.search(t)
    if m:
        c.doc = ident(m.group(1))
    return c


LIVED = r"\b(?:liv(?:e|ed|es|ing)|resid\w*|homes?|relocat\w*|mov(?:e|ed|es|ing)|based|worked|working|employ\w*|stay\w*|spent|grew up|previously|former|emigrat\w*|immigrat\w*)\b"
MONTH_WORDS = {"january", "february", "march", "april", "may", "june", "july", "august",
               "september", "october", "november", "december", "jan", "feb", "mar", "apr",
               "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "the", "a", "an"}


def sentences(t):
    return [x for x in re.split(r"(?<=[.;!?])\s+|\n+", t or "") if x.strip()]


PLACE_STOP = (r"\b(?:between|from|during|until|till|since|for|across|throughout|over|before|after"
              r"|when|while|with|as|where|which|who|that|because|but|then|spanning|spanned|within"
              r"|period|window|span|years?|duration|time|up)\b|\d|[;:()]")
GENERIC = {"work", "job", "a job", "jobs", "home", "employment", "residence", "business", "school",
           "university", "study", "studies", "family", "the area", "the country", "the city",
           "it", "there", "here", "person", "residency", "professional", "personal", "living",
           "working", "employ", "both", "and", "or", "abroad", "overseas"}


COMMON = set("""a an the this that these those his her their its our my your them they he she it we
you i me us user users customer customers client clients individual person people holder account
there here both all each either other same own was were is are be been being had has have do did
does employed employment employ living lived live lives working worked work works residing resided
reside resides residence residency resident career careers personal professional duties duty
spent spend job jobs role roles position positions capacity company firm office team area region
place places location locations country countries city cities town home homes life activities
activity covering cover based held holding hold kept keep various several many some time times
period periods years year months month while during as of on by with for job-related related
relation response reference context regard regards connection transfer transfers inquiry inquiries
enquiry question questions incoming outgoing international payment payments specifically records
record identified maintained maintain about regarding also previously formerly earlier later
to in at near s engaged professionally remained remain workforce timeframe recent recently
business school university study studies family abroad overseas purposes purpose reasons reason
part full basis stated declared reported confirmed said noted mentioned described verified
""".split())


def place_items(sent):
    """Items of every place list in a sentence: whatever follows in, to, at or
    near up to a time word, a number or a clause break, split on commas, and, or."""
    out = []
    for m in re.finditer(r"\b(?:in|to|at|near)\s+(.+)", sent, re.I):
        tail = m.group(1)
        stop = re.search(PLACE_STOP, tail, re.I)
        seg = tail[:stop.start()] if stop else tail
        seg = re.split(r"[.!?]\s", seg + " ")[0]
        for item in re.split(r",|\band\b|\bor\b|&|/", seg, flags=re.I):
            item = re.sub(r"^\s*(?:the|a|an)\s+", "", item.strip(" .'\""), flags=re.I).strip()
            words = re.findall(r"[^\W\d_]+", item.lower())
            # ordinary English words are prose, not places; anything else is kept
            if words and not all(w in COMMON for w in words):
                out.append(item)
    return out


def unresolved_places(sent):
    """Place list items that name no country we know, in any casing ("lagos").
    Such an item leaves the customer's country unknown."""
    out = []
    for item in place_items(sent):
        if countries.mentioned(item) or countries.norm(item) or countries.code_in_place(item.upper() if len(item) <= 3 else item):
            continue
        out.append(item)
    return out


MOVE = (r"\b(?:liv(?:e|ed|es|ing)|resid\w*|relocat\w*|mov(?:e|ed|es|ing)|based in|between|before"
        r"|after|previously|formerly|from|emigrat\w*|immigrat\w*|homes?|stay\w*|worked|working)\b")
WEEKDAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}


def unexplained_caps(sent, own=()):
    """Capitalised words in a residence sentence that are not a country, a month,
    a weekday, the customer's own name or an ordinary English word. Each one may
    be a place we cannot resolve."""
    out = []
    for m in re.finditer(r"\b[A-Z][\w'\-]*(?:\s+[A-Z][\w'\-]*)*", sent):
        seq = m.group(0)
        if countries.mentioned(seq) or countries.norm(seq) or countries.code_in_place(seq):
            continue
        words = [w.lower() for w in re.findall(r"[^\W\d_]+", seq)]
        if all(w in COMMON or w in MONTH_WORDS or w in WEEKDAYS or w in own or w in PROVIDERS
               for w in words):
            continue
        out.append(seq)
    return out


PROVIDERS = {"documentation", "verification", "according", "when", "identity", "throughout",
             "validation", "data", "information", "evidence", "upon", "details", "passport",
             "occupational", "within", "official", "files", "subject", "dates", "self", "reported",
             "self-reported", "following", "during", "as", "per", "having", "prior", "later", "earlier",
             "her", "his", "their", "this", "that", "these", "those", "there", "here", "following",
             "onfido", "sumsub", "veriff", "persona", "jumio", "kyc", "id", "dob", "uk", "us",
             "caller", "customer", "client", "user", "account", "holder", "individual", "on", "in",
             "between", "during", "after", "before", "from", "since", "until", "while", "per",
             "our", "internal", "file", "notes", "records", "record", "it", "they", "she", "he",
             "employment", "work", "residence", "professional", "residency", "employed", "living",
             "career", "job", "housing", "both", "documented", "is", "was", "were", "an", "a", "the"}


def caps_names(t):
    """Name parts of person names written in capitals in a note."""
    return {w for _, _, run in caps_runs(t) if name_like(run) for w in raw_parts(run)}


def note_residence(note, is_check, own=frozenset()):
    """Countries a note says the customer lived or worked in, and places it names
    that cannot be resolved. In an identity check note only the sentences about
    residence count, since the document country is read separately."""
    t = field(note, "text", "body", "note")
    found, unresolved = set(), []
    for sent in sentences(t):
        lived = re.search(LIVED, sent, re.I)
        if is_check and not lived:
            continue
        cs = countries.mentioned(sent) | countries.codes_in_prose(sent)
        found |= cs
        if lived or cs:
            # a list that names one country keeps its other items, resolved or not
            unresolved += unresolved_places(sent)
        moving = lived or re.search(r"\bbetween\s+[A-Z]|\bfrom\s+[A-Z][\w'\-]*(?:\s+[A-Z][\w'\-]*)*\s+to\s+[A-Z]|\bbased in\b|\bpreviously in\b", sent)
        if moving:
            # in a residence or movement sentence every place like word must be
            # explained; anything else may be a place we cannot resolve
            unresolved += unexplained_caps(sent, own | caps_names(t))
            if lived and not cs and not unresolved:
                unresolved.append(sent[:40])
    return found, unresolved


def note_places(note):
    """Countries a non identity note says the customer lived or worked in."""
    return note_residence(note, False)[0]


class Person:
    """All records that belong to one customer, and the facts they give."""

    def __init__(self, ids, db):
        self.ids = sorted(ids)
        self.records = [db.customers[i] for i in self.ids if i in db.customers]
        self.primary = self.ids[0]
        self.checks = []
        self.lived = []          # (note id, set of countries)
        self.places_unread = []
        self.unclear = []        # identity notes whose result we cannot read
        self.loose_names, self.loose_dobs = [], []
        self.emails = set()
        for r in self.records:
            e = field(r, "email").lower()
            if e:
                self.emails.add(e)
        seen = set()
        for cid in self.ids:
            for app in db.applicants_of(cid):
                for k in db.kyc_by_app.get(app, []):
                    kid = field(k, "check_id", "id")
                    if kid in seen:
                        continue
                    seen.add(kid)
                    res = field(k, "result", "status").lower()
                    chk = Check(
                        kid, dates.parse(field(k, "checked_at", "date")),
                        field(k, "verified_name", "name"),
                        dates.parse(field(k, "verified_dob", "dob")),
                        countries.norm(field(k, "document_country")),
                        res in APPROVED, "kyc", field(k, "verified_dob", "dob"))
                    chk.doc = ident(field(k, "document_number"))
                    chk.time = clock(field(k, "checked_at", "date"))
                    self.checks.append(chk)
        for e in sorted(self.emails):
            for n in db.notes_by_email.get(e, []):
                nid = field(n, "note_id", "id")
                if nid in seen:
                    continue
                seen.add(nid)
                c = note_check(n)
                if c:
                    self.checks.append(c)
                elif unclear_check(n):
                    self.unclear.append((dates.parse(field(n, "created_at", "date")), nid))
                if not c or not c.approved:
                    ln, ld = loose_facts(n)
                    self.loose_names += ln
                    self.loose_dobs += ld
                # residence statements count wherever they appear, check notes included
                own = frozenset(w for r in self.records for f in ("full_name", "preferred_name")
                                for w in raw_parts(field(r, f)))
                places, unresolved = note_residence(n, bool(c) or unclear_check(n), own)
                if places:
                    self.lived.append((nid, places))
                if unresolved:
                    self.places_unread.append(nid)
        self.checks.sort(key=Check.order)
        # principle 4: rejected and expired checks are not evidence
        self.approved = [c for c in self.checks if c.approved]
        self.latest = self.approved[-1] if self.approved else None
        # an unreadable identity note newer than the latest approved check might be
        # the real latest check, so the verified facts are not certain
        top = self.latest.order()[0] if self.latest else (0, 0, 0)
        self.verified_doubt = any((d is None) or dates.earliest(d) >= top
                                  for d, _ in self.unclear)
        # a completion only note newer than the latest approval may confirm but its
        # identity is not verified, so clearances treat the identity as unknown
        self.completed = [c for c in self.checks if c.completed and
                          (not self.latest or c.order()[0] >= top)]
        if self.completed:
            self.verified_doubt = True
        # an approval about a third party's document, or one with neither holder
        # nor birth date, leaves the verified identity unknown
        if self.latest and (self.latest.third_party or (self.latest.kind == "note" and
                                                         not self.latest.name and not self.latest.dob)):
            self.verified_doubt = True
        # a note that names a holder or birth date but is not a clean approval,
        # and differs from the latest approved identity, leaves that identity unknown
        lid = self.latest.identity() if self.latest else None
        for c in self.checks:
            if c.kind == "note" and not c.approved and getattr(c, "open", False) and (c.name or c.dob):
                if lid is None or (c.name and c.name.upper() != lid[0]) or (c.dob and c.dob != lid[1]):
                    self.verified_doubt = True
        # two approved checks on the latest day whose order cannot be told apart
        # (same instant, or a time missing on either) and that disagree leave the
        # latest identity unknown
        if self.latest:
            for c in self.approved[:-1]:
                same_day = c.order()[0] == top
                untimed = not c.time or not self.latest.time or c.time == self.latest.time
                if same_day and untimed and c.identity() != self.latest.identity():
                    self.verified_doubt = True

    def documents(self):
        """identifier -> record id: approved check document numbers and company
        registration numbers, at least 5 characters long."""
        out = {}
        for c in self.approved:
            if len(c.doc) >= 5:
                out.setdefault(c.doc, c.id)
        for r in self.records:
            v = ident(field(r, "registration_number"))
            if len(v) >= 5:
                out.setdefault(v, field(r, "record_id"))
        return out

    def entity_company(self):
        types = {kind(field(r, "entity_type", "type")) for r in self.records}
        if len(types) == 1:
            return types.pop()
        return None

    def verified_name(self):
        """The latest approved check's name. A note whose holder we could not
        bind leaves the verified name unknown."""
        for c in reversed(self.approved):
            if c.name:
                return c.name, c.id
            if c.kind == "note":
                return None, None
        return None, None

    def verified_unknown(self):
        """True when a verified identity exists or may exist but cannot be read:
        an unclassifiable identity note newer than the latest approved check, or
        a latest approved note whose holder could not be bound."""
        if self.verified_doubt:
            return True
        for c in reversed(self.approved):
            if c.name:
                return False
            if c.kind == "note":
                return True
        return False

    def dob(self):
        """(date, source id). The latest approved check that gives a date of birth
        wins; otherwise the record, preferring the fullest date."""
        self.dob_alts = []
        for c in reversed(self.approved):
            if c.dob:
                self.dob_alts = dates.readings(c.raw) if dates.ambiguous(c.raw) else []
                return c.dob, c.id
            if c.dob_unread:
                return None, None
        best = None
        company = self.entity_company()
        for r in self.records:
            raw = field(r, "dob", "date_of_birth", "incorporation_date")
            d = dates.parse(raw)
            # a system default birth date is unknown; old incorporation dates are real
            if not company and dates.placeholder(d):
                continue
            if d and (best is None or sum(x is not None for x in d) > sum(x is not None for x in best[0])):
                best = (d, field(r, "record_id"))
                self.dob_alts = dates.readings(raw) if dates.ambiguous(raw) else []
        return best if best else (None, None)

    def dob_readings(self):
        """Every reading of the customer's date of birth: two when day and month
        could swap, else one."""
        d, _ = self.dob()
        return self.dob_alts or ([d] if d else [])

    def record_names(self):
        out = []
        for r in self.records:
            for f in ("full_name", "preferred_name", "name"):
                v = field(r, f)
                if v:
                    out.append((v, field(r, "record_id")))
        return out

    def places(self):
        """country -> sorted list of record ids that tie the customer to it."""
        out = {}

        def add(c, src):
            if c:
                out.setdefault(c, set()).add(src)

        for r in self.records:
            rid = field(r, "record_id")
            for f in ("residence_country", "nationality", "country"):
                for v in multi(r.get(f)):
                    add(countries.norm(v), rid)
                    if countries.unread(v):
                        self.places_unread.append(v)
        if self.latest and self.latest.country:
            add(self.latest.country, self.latest.id)
        for nid, ps in self.lived:
            for c in ps:
                add(c, nid)
        return {k: sorted(v) for k, v in out.items()}


LISTING = {"sanctions": "a sanctioned individual", "pep": "a politically exposed person",
           "enforcement": "the subject of enforcement action",
           "adverse media": "named in adverse media",
           "soe": "a state-owned enterprise official"}
OTHER_LISTING = "named on a watchlist"

AGE_CUE = r"\b(?:age|aged|ages|years? old|year-old|born|birth)\b"

UNIT = r"(?:%|per ?cent|million|billion|thousand|people|persons|men|women|counts?|charges|times|grams|kg|months|days|years? (?:in|of) (?:prison|jail))"
THEN_AGE = r"\bthen\s+(?:aged\s+)?(\d{1,3})\b(?![.,]\d)(?!\s*" + UNIT + r")(?=\s*[,)]|\s+years?\b)"

AGE_PATTERNS = [
    r"\baged?\s*(?:of\s*)?:?\s*(\d{1,3})\b",
    r"\b(\d{1,3})\s*-?\s*years?\s*-?\s*(?:old|of age)\b",
    r"\b(\d{1,3})-year-old\b",
    r"\bage\b[^.;\d]{0,40}?\b(?:was|is|of)\s+(\d{1,3})\b",
    r"\b(?:was|is|reached|turned|aged)\s+(\d{1,3})\b(?![.,]\d)(?!\s*(?:%|per ?cent|people|persons|men|women|counts?|grams|kg|days|times|others|million|thousand))(?!\s*(?:years?|yrs?|months?)\b(?!\s*(?:old|of age)))",
    r"\bat\s+(\d{1,3})\b,",
]


UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in enumerate(
    "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}


def words_to_digits(text):
    """Ages written in words ("forty-five") become digits; same length is not kept,
    so call this only on text whose dates are already masked."""
    def tens(m):
        return str(TENS[m.group(1).lower()] + UNITS.get((m.group(2) or "").lower(), 0))
    t = re.sub(r"\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[\s-]+(one|two|three|four|five|six|seven|eight|nine))?\b",
               tens, text, flags=re.I)
    return re.sub(r"\b(%s)\b(?=[\s-]+(?:years?|year-old|yrs))" % "|".join(UNITS),
                  lambda m: str(UNITS[m.group(1).lower()]), t, flags=re.I)


RELATION = r"\b(?:father|mother|son|daughter|wife|husband|brother|sister|sibling|victim|child|children|girl|boy|baby|infant|co-?accused|co-?defendant|accomplice|nephew|niece|uncle|aunt|cousin|grandson|granddaughter|grandfather|grandmother|parent|stepson|stepdaughter|widow|fiancee?|girlfriend|boyfriend|partner)s?\b"
PRONOUN = r"\b(?:he|she)\b"


def age_at(text, subject=()):
    """An age at a date, bound to the subject: the age, the date and the
    subject's name (or he, she, they when the text names the subject) must sit in
    the same clause, and the clause must not be about someone else (a father, a
    victim). Returns (age, date) or None; clauses that disagree give None."""
    if not text:
        return None
    found = dates.find_all(text)
    if not found:
        return None
    masked = list(text)
    for a, b, _ in found:
        for i in range(a, b):
            masked[i] = " "
    m_text = "".join(masked)
    parts = {p for n in subject for p in raw_parts(n) if len(p) >= 2}
    named = not parts or bool(set(raw_parts(text)) & parts)
    results = set()
    start = 0
    for m in list(re.finditer(r"[.;!?\n]", m_text)) + [None]:
        end = m.start() if m else len(m_text)
        clause, ca = m_text[start:end], start
        start = end + 1
        ds = [d for a, b, d in found if ca <= a < end]
        if not ds or re.search(RELATION, clause, re.I):
            continue
        if parts and not (set(raw_parts(clause)) & parts or (named and re.search(PRONOUN, clause, re.I))):
            continue
        got = clause_age(words_to_digits(clause), ds, parts)
        if got:
            results.add(got)
    if len({tuple(years_from_age(*r)) for r in results}) != 1:
        return None
    return sorted(results)[0]


def record_block_age(text, parts):
    """A register extract: "information as of <date>:" followed by "Name:" and
    "Age:" lines. The age is tied to that date and to the named subject."""
    head = re.search(r"\bas of\s+([^:\n]{6,30}):", text, re.I)
    name = re.search(r"^\s*name\s*:\s*(.+)$", text, re.I | re.M)
    age = re.findall(r"^\s*age\s*:\s*(\d{1,3})\s*$", text, re.I | re.M)
    if not (head and name and len(age) == 1):
        return None
    if parts and not set(raw_parts(name.group(1))) & parts:
        return None
    d = dates.parse(head.group(1).strip())
    v = int(age[0])
    if d and 10 <= v <= 110:
        return v, d
    return None


def clause_age(clause, ds, parts=()):
    """The one age a clause states and the date it is tied to."""
    ages = set()
    for p in AGE_PATTERNS:
        for m in re.finditer(p, clause, flags=re.I):
            v = int(m.group(1))
            if 1 <= v <= 100:
                ages.add(v)
    for m in re.finditer(THEN_AGE, clause, flags=re.I):
        v = int(m.group(1))
        if 10 <= v <= 110:
            ages.add(v)
    if not ages:
        # comma style used by profiles and search results: "Jane Roe, 45, a ..."
        # or "listed 34, Jane Roe": the number must sit right next to the subject
        for m in re.finditer(r"([^\W\d_][\w'\-]*)\.?,\s*(\d{1,3})(?![\d.]\d)\s*[,)]", clause):
            if not parts or set(raw_parts(m.group(1))) & parts:
                ages.add(int(m.group(2)))
        for m in re.finditer(r"\b(?:listed|profiled|named|documented|featured|included|identified)\s+(\d{1,3}),\s*([^\W\d_][\w'\-]*)", clause):
            if not parts or set(raw_parts(m.group(2))) & parts:
                ages.add(int(m.group(1)))
        for m in re.finditer(r"([^\W\d_][\w'\-]*)\s+\((?:aged?\s*)?(\d{1,3})\)", clause):
            if not parts or set(raw_parts(m.group(1))) & parts:
                ages.add(int(m.group(2)))
        ages = {v for v in ages if 10 <= v <= 100}
    if len(ages) != 1:
        return None
    # dates of different years in one clause leave the reference date unknown
    if len({d[0] for d in ds}) != 1:
        return None
    ds = sorted(ds, key=lambda d: -sum(x is not None for x in d))
    return ages.pop(), ds[0]


def years_from_age(age, when):
    """Someone aged 45 in March 2019 was born in 1973 or 1974."""
    y = when[0]
    return [y - age - 1, y - age]


def first_paragraph(notes):
    t = (notes or "").strip()
    if not t:
        return ""
    return re.split(r"\n\s*\n", t)[0].strip()


DATED = re.compile(r"^\s*According to (.+?);\s*([A-Z][a-z]+\.? \d{1,2},? \d{4})\s*:", re.M)


class HitFacts:
    def __init__(self, hit, db):
        self.hit = hit
        self.id = field(hit, "hit_id", "id")
        self.company = kind(field(hit, "entity_type", "type")) is True
        self.type_known = kind(field(hit, "entity_type", "type")) is not None
        self.name = field(hit, "name")
        self.names = [self.name] if self.name else []
        for a in multi(hit.get("aliases")):
            if a not in self.names:
                self.names.append(a)
        self.places = self._places()
        self.notes = field(hit, "profile_notes", "notes")
        self.dob_kind = None     # listed, notes or search
        self.label_dobs = []
        self.dob_unread = False
        self.dob_src = []        # search result ids
        self.dobs = self._dobs(db)
        self.reports = self._reports()
        raw = field(hit, "deceased_date", "date_of_death")
        self.death = dates.parse(raw)
        self.deaths = dates.readings(raw) if dates.ambiguous(raw) else ([self.death] if self.death else [])
        self.death_src = "deceased_date"
        if not self.deaths and field(hit, "life_status").lower() == "deceased":
            # the profile states a death bound to the hit; every reading is kept
            found = [(c[0][0], c[1], c[2]) for c in bound_clause_dates(self.notes or "", self.names, DEATH_CUE, semicolons=False)
                     if len(c[0]) == 1]
            if found:
                self.deaths, self.death = found, found[0]
                self.death_src = "profile_notes"
        self.idents = set()
        for v in multi(hit.get("identifiers")):
            v = ident(v.split(":", 1)[-1])
            if len(v) >= 5:
                self.idents.add(v)

    def _places(self):
        out = set()
        h = self.hit
        self.places_unread = []
        for f in ("countries", "nationality", "citizenship", "addresses", "place_of_birth"):
            for v in multi(h.get(f)):
                part = countries.last_part(v)
                c = countries.norm(part)
                if c:
                    out.add(c)
                elif countries.unread(part):
                    self.places_unread.append(part)
        return out

    def category(self):
        cat = field(self.hit, "primary_category")
        if not cat:
            cats = multi(self.hit.get("categories"))
            cat = cats[0] if cats else ""
        return cat.strip().lower()

    def listing(self):
        return LISTING.get(self.category(), OTHER_LISTING)

    def _dobs(self, db):
        """List of candidates; each is (years, month, day) with years a list.
        Principle 5: the dobs field and the first paragraph of the profile notes
        both give birth dates; search results only when neither does."""
        listed = []
        for v in multi(self.hit.get("dobs")) + multi(self.hit.get("dob")):
            got = dates.parse_hits(v)
            if got:
                listed.extend(c for c in got if c not in listed)
            else:
                # an entry we cannot read may be the one that agrees
                self.dob_unread = True
        if self.company:
            # principle 5: for companies only the dobs field is an incorporation date
            self.dob_kind = "listed" if listed or self.dob_unread else None
            return listed
        para = first_paragraph(self.notes)
        noted = notes_dobs(para, self.names) if para else []
        # a bare "DOB:" label line is not one of principle 5's sources; it is kept
        # for the record but never supports a decision
        self.label_dobs = [c for m in DOB_LINE.finditer(para or "") for c in line_dates(m.group(1))]
        # a register extract ("information as of <date>:", "Age: 55") is a label
        # too: it may stop a clearance but never decides one
        block = record_block_age(para or "", {p for n in self.names for p in raw_parts(n) if len(p) >= 2})
        if block:
            self.label_dobs.append((years_from_age(*block), None, None))
        rest = re.sub(r"(?im)^\s*age\s*:\s*\d{1,3}\s*$", " ", DOB_LINE.sub(" ", para or ""))
        if para and not noted and re.search(AGE_CUE, rest, re.I) and dates.find_all(rest):
            # the profile states an age or birth we cannot read: unknown, and
            # it may be the agreement that stops a location clearance
            self.dob_unread = True
        if listed and noted:
            self.dob_kind = "listed and notes"
        elif listed or (self.dob_unread and not noted):
            self.dob_kind = "listed" if listed or multi(self.hit.get("dobs")) else None
        elif noted:
            self.dob_kind = "notes"
        if listed or noted:
            return listed + noted
        if self.dob_kind == "listed":
            return []
        out = []
        listing = self.listing()
        own = set(raw_parts(self.name))
        for r in db.search_for(self.name):
            snip = field(r, "snippet", "text")
            if listing not in snip.lower():
                continue
            masked = " ".join(w for w in re.split(r"(\s+)", snip) if not set(raw_parts(w)) & own)
            if not (countries.mentioned(masked) & self.places):
                continue
            full = [c for c in born_in(snip) if c[1]]
            for m in DOB_LINE.finditer(snip):
                full += line_dates(m.group(1))
            got = age_at(snip, self.names)
            if full:
                # a result that states a birth date gives it directly
                out.extend(c for c in full if c not in out)
                self.dob_src.append(field(r, "result_id", "id"))
            elif got:
                out.append((years_from_age(*got), None, None))
                self.dob_src.append(field(r, "result_id", "id"))
            else:
                # a result about the hit whose age we cannot read: the hit's date
                # of birth is unknown rather than absent
                self.dob_unread = True
        if out:
            self.dob_kind = "search"
        return out

    def _reports(self):
        out = []
        for m in DATED.finditer(self.notes or ""):
            d = dates.parse(m.group(2))
            if d:
                out.append(d)
        return sorted(out)


DOB_LINE = re.compile(r"(?:^|[\n;.]\s*|\b)(?:dob|d\.o\.b\.?|date of birth|birth ?date)\s*[:\-]\s*([^\n]{4,60})", re.I)


def line_dates(value):
    """Every birth date a labelled value gives, alternatives included."""
    value = re.split(r"(?<!\b[a-z])\.\s|;\s*(?=[A-Za-z])", value)[0].strip()
    got = dates.parse_hits(value)
    if got:
        return got
    out = []
    for a, b, d in dates.find_all(value):
        for c in dates.parse_hits(value[a:b]) or [([d[0]], d[1], d[2])]:
            if c not in out:
                out.append(c)
    return out


def clauses(text):
    """(start, end) of each clause; dates are masked first so their dots and
    slashes never split a clause."""
    found = dates.find_all(text)
    masked = list(text)
    for a, b, _ in found:
        for i in range(a, b):
            masked[i] = " "
    m_text = "".join(masked)
    out, start = [], 0
    depth = []
    level = 0
    for i, ch in enumerate(m_text):
        level += (ch == "(") - (ch == ")")
        depth.append(level)
    # a separator inside brackets ("born 1950; 1980") does not end the clause
    seps = [m for m in re.finditer(r"[.;!?\n]", m_text) if depth[m.start()] <= 0 or m.group() == "\n"]
    for m in seps + [None]:
        end = m.start() if m else len(m_text)
        if end > start:
            out.append((start, end))
        start = end + 1
    return out, found


def bound_to_subject(clause, parts, named):
    """The clause is about the hit: it names the hit (or says he or she when the
    text names the hit) and mentions no relative, victim or associate."""
    if re.search(RELATION, clause, re.I) or re.search(r"\bassociate\w*\b", clause, re.I):
        return False
    if not parts:
        return True
    return bool(set(raw_parts(clause)) & parts) or (named and bool(re.search(PRONOUN, clause, re.I)))


def notes_dobs(para, subject=()):
    """Birth dates stated in a profile's first paragraph and bound to the hit:
    labelled lines such as "DOB: 6/20/1955", a "born" clause about the hit, or
    else an age at a date. Every alternative is kept."""
    out = []
    for c in named_birth(para, subject):
        if c not in out:
            out.append(c)
    for c in born_in(DOB_LINE.sub(" ", para), subject):
        if c not in out:
            out.append(c)
    if not out:
        got = age_at(DOB_LINE.sub(" ", para), subject)
        if got:
            out.append((years_from_age(*got), None, None))
    return out


BETWEEN_OK = (r"^[\s,]*(?:\([^)]*\)[\s,]*)?(?:,[^,]{0,40},\s*)?(?:who\s+)?(?:was|is|were|had been|has been)?\s*"
              r"(?:reportedly|reported to have been|believed to have been|said to have been|thought to have been)?\s*$")


def born_subject(clause, at, parts, named):
    """The birth predicate attaches to the hit: no negation in the clause, and
    between the hit's name (or he, she) and "born" only a verb such as was, an
    aside without another person's name, or nothing; "Born on <date>, <hit>" at
    the start of a clause also counts."""
    if re.search(r"\b(?:not|never|no)\b|n['\u2019]t\b", clause, re.I):
        return False
    before = clause[:at]
    if not before.strip() or re.fullmatch(r"\s*", before):
        return True
    last = None
    for m in re.finditer(r"[^\W\d_][\w'\-]*", before):
        w = m.group(0)
        if (parts and set(raw_parts(w)) & parts) or (named and w.lower() in ("he", "she")):
            last = m.end()
    if last is None:
        return False
    between = before[last:]
    others = [w for w in re.findall(r"\b[A-Z][\w'\-]*", between) if not (set(raw_parts(w)) & parts)]
    return not others and bool(re.match(BETWEEN_OK, between))


BIRTH_CUE = r"\b(?:date of birth|birth ?date|dob|d\.o\.b\.?)\b"
DEATH_CUE = r"\b(?:died|date of death|death date|deceased|passed away)\b"
NEGATION = r"\b(?:not|never|no)\b|n['\u2019]t\b"


# words for other people; a birth or death in a clause that mentions one may be theirs
PERSON_NOUNS = (r"\b(?:colleague|friend|associate|man|woman|person|people|officer|official|client"
                r"|customer|neighbou?r|employee|employer|boss|lawyer|witness|suspect|defendant|accused"
                r"|member|leader|predecessor|successor|relative|family|household|someone|another|others?)s?\b")


def bound_clause_dates(text, subject, cue, semicolons=True):
    """Dates a clause gives for the hit under a cue (a birth or death phrase):
    the clause names the hit, has no negation, no relative and no other person's
    name, and the dates sit in that clause."""
    parts = {p for n in subject for p in raw_parts(n) if len(p) >= 2}
    if not parts:
        return []
    named = bool(set(raw_parts(text)) & parts)
    spans, found = clauses(text if semicolons else text.replace(";", ","))
    out = []
    for a, b in spans:
        clause = text[a:b]
        if not re.search(cue, clause, re.I) or re.search(NEGATION, clause, re.I):
            continue
        if not bound_to_subject(clause, parts, named) or re.search(PERSON_NOUNS, clause, re.I):
            continue
        # another capitalised name in the clause may be the real subject
        words = re.findall(r"\b[A-Z][a-z][\w'\-]*\b", clause)
        others = [w for w in words if not (set(raw_parts(w)) & parts)
                  and w.lower() not in COMMON and w.lower() not in PROVIDERS and w.lower() not in MONTH_WORDS
                  and not countries.mentioned(w)]
        if len(others) > 1 or any(w[0].isupper() and clause.find(w) > 0 and w not in ("He", "She") and
                                  not re.match(r"[A-Z]", clause.strip()) for w in others):
            continue
        for x, y, d in found:
            if a <= x < b:
                for c in dates.parse_hits(text[x:y]) or [([d[0]], d[1], d[2])]:
                    if c not in out:
                        out.append(c)
    return out


def named_birth(para, subject):
    """A first paragraph sentence that states the hit's birth date under a birth
    phrase ("The birth date recorded for <hit> is ...")."""
    return bound_clause_dates(para, subject, BIRTH_CUE)


def profile_appositive(text, clause, parts):
    """"Croatian politician (born 1967)": a description that names nobody, so the
    birth in brackets belongs to the profile's subject."""
    if not re.search(r"\(\s*born\b", clause, re.I) or re.search(RELATION, text, re.I) \
            or re.search(NEGATION, clause, re.I):
        return False
    words = re.findall(r"\b[A-Z][\w'\-]*", text)
    others = [w for w in words if not (set(raw_parts(w)) & parts) and not countries.mentioned(w)
              and w.lower() not in COMMON and w.lower() not in MONTH_WORDS]
    return not others


def born_in(text, subject=()):
    """Candidates from "X was born in 1950 or 1980" style clauses about the hit;
    every date in the clause after "born" is kept, and an ambiguous numeric date
    gives both readings."""
    parts = {p for n in subject for p in raw_parts(n) if len(p) >= 2}
    named = not parts or bool(set(raw_parts(text)) & parts)
    spans, found = clauses(text)
    out = []
    for a, b in spans:
        clause = text[a:b]
        m = re.search(r"\bborn\b", clause, re.I)
        if not m:
            continue
        if not (profile_appositive(text, clause, parts) or
                (bound_to_subject(clause, parts, named) and born_subject(clause, m.start(), parts, named))):
            continue
        for x, y, d in found:
            if a + m.end() <= x < b:
                for c in dates.parse_hits(text[x:y]) or [([d[0]], d[1], d[2])]:
                    if c not in out:
                        out.append(c)
    return out
