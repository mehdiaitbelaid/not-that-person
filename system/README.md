# Not That Person: a rules engine for screening hits

`system/run <data folder> <output file>` writes one JSON line per hit. Python 3 standard library only, no network, no language model.

The engine aims to clear only on a contradiction the policy names, confirm only on agreement, and otherwise leave the hit to a person; this rests on reading free text correctly (see Known limits). Every decision can be replayed from its inputs and cites the records that decided it.

## Architecture

```
 +-------+     +------------------------------+     +--------------------------+
 | alert | --> | link: account_ref,           | --> | candidate records        |
 +-------+     | login_handle or email        |     | screened name, DOB,      |
     |         +------------------------------+     | country, city pick       |
     |  no link                                     | between joint holders    |
     +--> search records by name, DOB, ------------>+--------------------------+
          country and city                                       |
                                                                 v
                  +----------------------------------------------------------+
                  | person clustering: same phone + same full DOB, or same   |
                  | document number on approved checks, followed transitively|
                  +----------------------------------------------------------+
                         |                                   |
                         v                                   v
        +-------------------------------+   +-----------------------------------+
        | customer facts                |   | hit facts                         |
        | latest approved check (KYC    |   | dobs field                        |
        | table or note), record DOBs,  |   | first paragraph of profile notes  |
        | countries, residence notes    |   | qualifying search results         |
        +-------------------------------+   | countries, dated reports, death   |
                         |                  +-----------------------------------+
                         +-----------------+-----------------+
                                           v
        +------------------------------------------------------------------+
        | contradiction tests in fixed order: entity type, deceased,       |
        | 16 year rule, DOB, location, verified name                       |
        +------------------------------------------------------------------+
               | one holds --> DIFFERENT_ENTITY
               v none
        +------------------------------------------------------------------+
        | agreement test: name + DOB (+ country) for people,               |
        | name + country for companies                                     |
        +------------------------------------------------------------------+
               | holds --> SAME_ENTITY
               v
           REVIEW by default
               |
               v
        reason (2 to 4 sentences) and evidence (record IDs that decided it)
```

## Finding the customer and the listed person

The alert's link gives candidate records; the screened details choose between joint holders. Without a link, an index of name parts, variants, joined forms and near spellings retrieves records, which are kept when they fit the screened name, date of birth (either reading), country and city. `tools/retrieval_check.py` compares this with a full scan on 60 unlinked dev alerts and 13 synthetic names; none was missing (not rerun for this README). Records are merged into one person by phone plus full date of birth, or a shared document number on approved checks. If several people fit, each is decided; one common decision is given with `AMBIGUOUS`, otherwise `REVIEW / AMBIGUOUS_CUSTOMER_RECORD`.

Verified facts come from the latest approved check, in the KYC table or a note; rejected, expired and pending checks are ignored. Countries come from the person's records, approved document and residence statements.

Hit birth dates come from the `dobs` field and the first paragraph of the profile notes ("was born on", "aged 45 in March 2019"; a bare "DOB:" label line is not used), and from search results only when neither gives one. A search result counts only with the category's listing phrase and a country tied to the hit. Dated reports are only lines of the form "According to …; Month D, YYYY:".

## Evidence

Every fact keeps the ID of its source record. The output's `evidence` list holds only the IDs behind the decisive test. When a test cannot run because a fact is missing, the reason says which fact, as in H-427D39 below.

## Same results on every run

Sorting and record IDs fix order and ties; nothing reads the clock or randomness. We run five times on `data/official_room/dev`, from four working directories and once with another `PYTHONHASHSEED`, and compare SHA-256: all gave `c47fbe0f…3d5e72`.

## Model, prompts, time and cost

No model, no prompts. A full dev run (819 hits, 72,265 customer records, 86,659 accounts) takes about 8 s on an Apple M3 Pro with Python 3.13.9; a rerun while other jobs ran took 12.7 s. Cost is zero. The dev output holds 462 `DIFFERENT_ENTITY`, 125 `SAME_ENTITY` and 232 `REVIEW`.

## Three cases

H-13E1CF, `DIFFERENT_ENTITY / TEMPORAL_IMPOSSIBILITY`. ACC-B3E19A leads to CUS-364225, which shares phone and full date of birth with CUS-851234, so both are one person. KYC-358C76 is the approved check and verifies a 2007 birth date. The hit's earliest dated report is 2020-01-08, when the customer was under 16; the reason states the bound from years alone, at most 13. The time test outranks the country mismatch the reason also notes.

H-A72A50, `SAME_ENTITY / NAME_DOB_LOCATION_MATCH`. ACC-6A9A74 has holders CUS-186144 and CUS-546084; only CUS-186144 fits the screened name and date of birth. CUS-977888 shares both and joins CUS-186144. KYC-6075EB verifies 1962-10-23, agreeing with the hit's 1962; name and United States agree.

H-427D39, `REVIEW / INSUFFICIENT_DATA`. ACC-7FB32A leads to CUS-762804, whose own record shares no country with the hit, so on its own it would clear on location. Clustering adds CUS-510447, and it and NOTE-7F183D tie the customer to India, the hit's country. Countries overlap and names agree, but the hit gives no birth date, so I leave it to a person.

## How we tested it

The organisers' `validate.py` on the 50 practice labels:

```
819 lines read, 0 problems
practice labels: 50 hits, 50 right decisions, 0 unsafe clearances
decision score 100.0 (0 = all REVIEW, 100 = perfect)
on right decisions: reason code 100%, customer record 100%
```

62 of 62 independent policy fixtures pass; they test the reading of the policy only.

A blind second implementation disagreed on 56 dev hits; we adjudicated 55 by hand and found none of our clearances unsafe (not rerun for this README).

A rewording probe paraphrases the notes and profile sentences the engine reads and adds traps: pending and negated checks, sentence lengths, other people's ages, ambiguous numeric dates, bare country codes. `tools/regressions.py` holds the failing inputs of two external reviews plus generated variants of each failure class; all 409 are left uncleared.

A stress probe on human judged OpenSanctions pairs (CC BY-NC, testing only, not in this repository) found script and placeholder bugs, now fixed; it measures no accuracy.

`tools/invariants.py` fails an output when a location, DOB or name clearance coexists with name and DOB agreement, a clearance lacks a customer or clears `AMBIGUOUS` without every candidate clearing, a code does not fit its decision, an evidence ID is unknown, a hit is missing or duplicated, or a reason is outside 2 to 4 sentences.

## Known limits

Free text is read with word lists and patterns, tested on dev wording and generated variants only; approval, negation, holder, birth subject and place rules all depend on them. When the verified identity cannot be read, no location clearance is given. Known holes: an age negated or attached to another person in its clause, another person's birth year in a separate clause, an unlisted verb before a lowercase place, and another named person's death or birth in a sentence naming the hit. A note saying only that a check "concluded" or "was processed" may confirm, never clear. Names in different scripts are treated as not comparable, with no transliteration.

Guards beyond the policy: a shared approved document number blocks clearance; placeholder birth dates (1900-01-01, years before 1900) are unknown for clearing or confirming but still merge records.

Numeric dates whose day and month could swap are kept in both readings in checks, records, screened details, profile birth clauses and death dates, and tested there; a contradiction must hold under every reading. Joined name forms must match exactly. Countries come from a static ISO 3166 table, so a place outside it stays unresolved.
