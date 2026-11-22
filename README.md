<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <img src="assets/logo.svg" alt="Not That Person logo" width="88">
  </picture>
</p>

<h1 align="center">Not That Person</h1>

<p align="center">Sanctions screening that tells namesakes apart.</p>

<p align="center">
  <a href="https://drive.google.com/file/d/1vnlUbjOXMf5WqmvwMeri0xTO94_kCu9Z/view">Demo video</a>
  ·
  <a href="system/README.md">Technical write up</a>
</p>

A bank's screening system flags a customer when their name matches someone on a sanctions list. Most of those hits are namesakes. Clearing the wrong one is the worst mistake a screening team can make, so this engine never clears on a similarity score. It clears a hit only when the bank's own records prove a contradiction, confirms it only when the identities agree (name and date of birth for a person, name and country for a company), and sends everything else to a person.

Built in one day for Track 2 of the Grok Bot London Financial Crime Hackathon (21 November 2026), on a track designed by Diligent.

## Results

| Measure | Result |
|---|---|
| Development hits decided | 819 in about 8 seconds |
| Practice labels | 50 of 50 right, 0 unsafe clearances |
| Three unseen test sets, 300 hits each | 297, 297 and 280 right, 0 unsafe clearances |
| Same output on every run | 5 of 5 runs byte identical |
| Model calls, cost per alert | none |

The development output splits into 462 cleared, 125 confirmed and 232 sent to a person.

## Run it

Python 3, standard library only. No install, no network, no API key.

```bash
system/run <data folder> <output file>
```

It writes one JSON line per hit: the decision (`DIFFERENT_ENTITY`, `SAME_ENTITY` or `REVIEW`), a reason code, the customer record it resolved to, a short reason and the IDs of the records that decided it. `output/dev.jsonl` is the run on the hackathon's development set. The data itself belongs to the organisers and is not in this repository.

## How it decides

1. Follow the alert to the bank's customer, and merge records that are the same person (same phone and full birth date, or the same approved document number).
2. Read the facts on both sides: the customer's latest approved identity check and records, and the listed person's names, birth dates, countries and death.
3. Clear only on a contradiction the policy names: birth dates that cannot both be true, no shared country, a verified name that does not match, a person against a company, a listed person who died before the activity, or a customer who was a child at the time.
4. Confirm only when name and birth date agree (name and country for a company). Everything else goes to a person.

Each step and its limits are in [system/README.md](system/README.md), with three worked cases.

## Known limits

Free text is read with word lists and patterns. A note that approves an ID but rejects something unrelated, such as a card payment, is treated as unreadable, so the engine will not clear or confirm on the strength of that note. Some of those hits end up with a person when the records could have decided them. Names in different scripts are not transliterated.

## Repository

```
system/    the engine and its technical README
output/    predictions on the development set
assets/    logo
```

The commit judged at code freeze is tagged `v1.0-submission`.
