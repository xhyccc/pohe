# POHE — Pattern-Oriented Harness Engineering field guide

A static field guide to 52 candidate harness records for AI agents: execution
loops, workflows, communication structures, reasoning and feedback mechanisms,
and harness-evolution research. Each record shows a proposed pointcut, a
protected contract, permitted variation, an analytical object-interaction
model, and the evidence layer behind it.

Published at **https://xhyccc.github.io/pohe/**

## What this site is

- A generated, deterministic rendering of frozen study artifacts. Nothing is
  computed at request time, and the site makes no network calls.
- An **evidence-layered** catalog. A retrieval cue is not a confirmed
  implementation, a source anchor is one exemplar and not a prevalence
  estimate, and the 52 records are a scoped candidate inventory.
- A **proposed** discipline. Specifications, contracts, and analytical
  interaction diagrams describe intended obligations; they do not certify any
  repository's behavior.

The catalog deliberately keeps these boundaries visible instead of compressing
them into a single confidence score.

## Structure

```
index.html                  catalog with search/filter/deep links
method.html                 evidence key, frozen inputs, and reproduction
patterns/<ID>/index.html     one detail page per record
data/patterns.json          generated catalog data
assets/diagrams/            SVG + PDF interaction diagrams (one pair per record)
assets/paper/               the complete position paper PDF
assets/styles.css           local stylesheet (light/dark, responsive, print)
assets/site.js              filter + navigation logic (no network)
scripts/generate_site.py    deterministic generator
tests/validate_site.py      stdlib integrity and accessibility checks
```

## Rebuild

The generator reads the companion study checkout and manuscript by default.
PyYAML is used when available, with a stdlib-only fallback parser.

```sh
python3 scripts/generate_site.py
python3 -I tests/validate_site.py
python3 -m http.server 8000
```

Override the inputs with `--study /path/to/pattern-mining-study` and
`--paper /path/to/main.pdf`. Generated files are the output of the script; edit
the generator rather than the rendered HTML.

## Evidence boundaries

- 52 records across five source families (P, W, C, R, E).
- 41 repositories / 36 repository families in the frozen audit panel.
- 51 of 52 records have a canonical source anchor; E08 is specification-only.
- Human validation, detector validation, and the H1/H2 causal studies remain
  open. The study's 200 role-conditioned profiles are one model's consistency
  under different prompts, not independent human agreement.

## License

The site content summarizes an unpublished research manuscript. The
interaction diagrams and catalog text are provided for review and discussion.
Canonical source anchors link to the named public implementation repositories
at the recorded commit; follow each repository's own license.
