#!/usr/bin/env python3
"""Generate the standalone POHE field guide from the frozen study artifacts.

PyYAML is used when installed so the frozen protocol files parse exactly as the
study reads them; a small stdlib-only YAML reader remains as a fallback.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pattern_examples import EXAMPLES  # noqa: E402
FAMILIES = {
    "P": ("Coding-agent mechanisms", "Execution loops, tools, authority, durable state, and stop-time checks."),
    "W": ("Workflows & coordination", "Named workflows and coordination forms from official agent guides."),
    "C": ("Communication", "Classical communication structures applied to agent systems."),
    "R": ("Reasoning & feedback", "Reason–act and verbal-feedback mechanisms."),
    "E": ("Harness evolution", "Research mechanisms that adapt or search over harnesses."),
}
ACTIVITIES = {
    "A1": "Design & implementation",
    "A2": "Testing & verification",
    "A3": "Maintenance & evolution",
}
EXPECTED_IDS = (
    [f"P{i:02d}" for i in range(1, 30)]
    + [f"W{i:02d}" for i in range(1, 8)]
    + [f"C{i:02d}" for i in range(1, 5)]
    + [f"R{i:02d}" for i in range(1, 3)]
    + [f"E{i:02d}" for i in range(1, 11)]
)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def scalar(value: str):
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1]
        return [scalar(part) for part in next(csv.reader([inner], skipinitialspace=True))]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    if value.lower() == "false":
        return False
    if value.lower() == "true":
        return True
    return value


def yaml_load(text: str):
    """Read a POHE protocol file.

    PyYAML is used when available so quoted values, folded scalars, and inline
    with indication syntax parse exactly as the study reads them. The bundled
    conservative parser remains as a stdlib-only fallback.
    """
    try:
        import yaml
    except ImportError:  # pragma: no cover - exercised only without PyYAML
        yaml = None
    if yaml is not None:
        return yaml.safe_load(text)
    raw = [(len(line) - len(line.lstrip(" ")), line.strip()) for line in text.splitlines()]
    lines = [(indent, content) for indent, content in raw if content and not content.startswith("#")]

    def block(start: int, indent: int):
        is_list = lines[start][1].startswith("- ") or lines[start][1] == "-"
        result = [] if is_list else {}
        i = start
        while i < len(lines):
            level, content = lines[i]
            if level < indent:
                break
            if level > indent:
                raise ValueError(f"Unexpected indentation near {content!r}")
            if is_list:
                if not content.startswith("-"):
                    break
                item = content[1:].strip()
                if not item:
                    value, i = block(i + 1, lines[i + 1][0])
                    result.append(value)
                    continue
                if re.match(r"^[^:\[\]]+:\s*", item):
                    key, val = item.split(":", 1)
                    entry = {}
                    if val.strip():
                        entry[key.strip()] = scalar(val)
                        i += 1
                    else:
                        value, i = block(i + 1, lines[i + 1][0])
                        entry[key.strip()] = value
                    if i < len(lines) and lines[i][0] > indent:
                        extra, i = block(i, lines[i][0])
                        entry.update(extra)
                    result.append(entry)
                    continue
                result.append(scalar(item))
                i += 1
                continue
            if content.startswith("- "):
                break
            key, val = content.split(":", 1)
            key = key.strip()
            val = val.strip()
            if val == ">":
                parts = []
                i += 1
                while i < len(lines) and lines[i][0] > indent:
                    parts.append(lines[i][1])
                    i += 1
                result[key] = " ".join(parts)
            elif val:
                result[key] = scalar(val)
                i += 1
            else:
                if i + 1 >= len(lines) or lines[i + 1][0] <= indent:
                    result[key] = {}
                    i += 1
                else:
                    value, i = block(i + 1, lines[i + 1][0])
                    result[key] = value
        return result, i

    if not lines:
        return {}
    value, end = block(0, lines[0][0])
    if end != len(lines):
        raise ValueError(f"Could not parse YAML line {end + 1}: {lines[end]!r}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = content.rstrip() + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")


def source_url(repo: str, commit: str, locator: str) -> str:
    match = re.match(r"^(.*):(\d+)$", locator)
    path, line = (match.group(1), match.group(2)) if match else (locator, "")
    url = f"https://github.com/{repo}/blob/{commit}/{quote(path, safe='/')}"
    return f"{url}#L{line}" if line else url


def nav(prefix: str, current: str) -> str:
    return f"""
<a class="skip-link" href="#main-content">Skip to content</a>
<header class="site-header">
  <a class="wordmark" href="{prefix}./" aria-label="POHE field guide home">
    <svg class="mark" viewBox="0 0 42 42" aria-hidden="true"><path d="M4 4h34v34H4zM4 14h34M14 4v34M14 14l12 12M26 14v12H14"/><circle cx="14" cy="14" r="2.5"/><circle cx="26" cy="26" r="2.5"/></svg>
    <span><strong>POHE</strong><small>Engineering field guide</small></span>
  </a>
  <button class="nav-toggle" id="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav"><span>Index</span><i aria-hidden="true"></i></button>
  <nav class="site-nav" id="site-nav" aria-label="Primary navigation">
    <a href="{prefix}./#catalog"{' aria-current="page"' if current == 'catalog' else ''}>Catalog <sup>52</sup></a>
    <a href="{prefix}method.html"{' aria-current="page"' if current == 'method' else ''}>Method & evidence</a>
    <a class="personal-link" href="https://xhyccc.github.io/">Website <span aria-hidden="true">↗</span></a>
    <a class="paper-link" href="{prefix}assets/paper/pohe-position.pdf">Read the paper <span aria-hidden="true">↗</span></a>
  </nav>
</header>""".strip()


def realization_files(anchors: list[dict], realizations: list[dict], limit: int = 5) -> list[dict]:
    """Pick a canonical exemplar plus source-first cue realizations from distinct repos."""
    files: list[dict] = []
    seen_repos: set[str] = set()
    for anchor in anchors:
        if anchor.get("kind") != "source":
            continue
        repo = str(anchor["repo_slug"])
        seen_repos.add(repo)
        locator = str(anchor["implementation"])
        match = re.match(r"^(.*):(\d+)$", locator)
        path, line = (match.group(1), int(match.group(2))) if match else (locator, None)
        files.append(
            {
                "repo": repo,
                "path": path,
                "line": line,
                "url": str(anchor["url"]),
                "kind": "canonical source",
            }
        )
    ordered = sorted(
        realizations,
        key=lambda row: (
            0 if str(row["realization_status"]).startswith("source") else 1,
            str(row["repo_slug"]).lower(),
            str(row["representative_path"]),
        ),
    )
    for row in ordered:
        if len(files) >= limit:
            break
        repo = str(row["repo_slug"])
        if repo in seen_repos:
            continue
        seen_repos.add(repo)
        path = str(row["representative_path"])
        line = int(row["representative_line"]) if str(row["representative_line"]).isdigit() else None
        files.append(
            {
                "repo": repo,
                "path": path,
                "line": line,
                "url": source_url(repo, str(row["first_introduced_commit"]), f"{path}:{line}" if line else path),
                "kind": "retrieval cue",
            }
        )
    return files


def shell(title: str, description: str, body: str, prefix: str = "", current: str = "", canonical: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{esc(description)}">
  <meta name="theme-color" content="#f2eee4">
  <title>{esc(title)}</title>
  <link rel="canonical" href="https://xhyccc.github.io/pohe/{esc(canonical)}">
  <link rel="stylesheet" href="{prefix}assets/styles.css">
  <script src="{prefix}assets/site.js" defer></script>
</head>
<body>
{nav(prefix, current)}
{body}
<footer class="site-footer">
  <div><strong>POHE</strong> / Pattern-Oriented Harness Engineering<br><span class="footer-author">Haoyi Xiong</span></div>
  <p>A proposed discipline for recurring harness decisions. Specifications and analytical diagrams do not certify implementations.</p>
  <div class="footer-links"><a href="{prefix}method.html#evidence-key">How to read the evidence</a><a href="{prefix}method.html#colophon">Colophon</a></div>
  <p class="footer-disclosure">Analytical diagrams, prompt sketches, and code designs describe proposed contracts. They are not observed traces, repository class declarations, or evidence that any implementation conforms.</p>
</footer>
</body>
</html>"""


def catalog_row(p: dict) -> str:
    evidence = [p["evidence"]["status"], "current_cue" if p["evidence"]["current_cue_repositories"] else "no_current_cue"]
    search = " ".join([p["id"], p["name"], p["problem"], p["join_point"], p["family_name"], *p["activity_names"]]).lower()
    activity = " · ".join(p["activities"])
    source = "Source-located" if p["evidence"]["status"] == "source_located" else "Specification only"
    observed = p["evidence"]["family_observed"]
    total = p["evidence"]["family_total"]
    coverage = round(100 * p["evidence"]["family_coverage"])
    return f"""<article class="pattern-row" data-pattern="true" data-family="{p['family']}" data-activities="{' '.join(p['activities'])}" data-evidence="{' '.join(evidence)}" data-search="{esc(search)}">
  <a class="pattern-row-link" href="patterns/{p['id']}/" aria-label="{p['id']}: {esc(p['name'])}">
    <span class="pattern-code">{p['id']}</span>
    <span class="pattern-main"><strong>{esc(p['name'])}</strong><span>{esc(p['problem'])}</span></span>
    <span class="pattern-activity"><b>{activity}</b><small>{source}</small></span>
    <span class="row-coverage" aria-label="Any-evidence coverage: {observed} of {total} repository families"><span class="coverage-track"><i style="width:{coverage}%"></i></span><small>{observed}<b>/{total}</b></small></span>
    <span class="row-arrow" aria-hidden="true">↗</span>
  </a>
</article>""".strip()


def render_index(patterns: list[dict]) -> str:
    family_options = "".join(f'<option value="{key}">{key} — {esc(value[0])}</option>' for key, value in FAMILIES.items())
    activity_options = "".join(f'<option value="{key}">{key} — {esc(value)}</option>' for key, value in ACTIVITIES.items())
    family_counts = Counter(p["family"] for p in patterns)
    family_rules = "".join(f"""<a href="#catalog" class="family-rule" data-family="{key}" data-family-link="{key}"><span class="family-code">{key}</span><strong>{esc(value[0])}</strong><small>{esc(value[1])}</small><span class="family-count">{family_counts[key]} records</span></a>""" for key, value in FAMILIES.items())
    rows = "\n".join(catalog_row(p) for p in patterns)
    body = f"""
<main id="main-content">
  <section class="hero" aria-labelledby="hero-title">
    <div class="hero-kicker"><span>Field guide № 01</span><span>Proposed pattern discipline</span></div>
    <div class="hero-grid">
      <div>
        <h1 id="hero-title">Pattern-Oriented<br><em>Harness Engineering<span class="hero-title-colon">:</span></em><span class="hero-title-sub">Design Patterns when OOD meets Agentic AI</span></h1>
        <p class="hero-deck">A field guide to the recurring decisions around AI agents: what may vary, what must hold, and what happens when it does not.</p>
        <div class="hero-actions"><a class="button button-primary" href="#catalog">Browse the 52 records <span aria-hidden="true">↓</span></a><a class="text-link" href="method.html">Read the method <span aria-hidden="true">↗</span></a></div>
      </div>
      <aside class="hero-note" aria-label="Position statement">
        <span class="note-label">Position / 001</span>
        <p>Scaling alone cannot absorb a harness’s system responsibilities. Name the join point. Protect the contract. Test the violation path. Record the lifecycle.</p>
        <a class="note-map-link" href="#a2-map"><span>A² taxonomy</span><strong>See the two-axis map</strong><i aria-hidden="true">↓</i></a>
      </aside>
    </div>
    <figure class="hero-map" id="a2-map">
      <a class="hero-map-frame" href="assets/a2/taxonomy-a2.svg" aria-label="Open the full A² taxonomy map as SVG">
        <img src="assets/a2/taxonomy-a2.svg" width="1120" height="690" alt="A-squared taxonomy: three activities—design, verification, and evolution—cross protected contracts and permitted variation, with an authorized re-generalization return from maintenance to design." loading="lazy">
      </a>
      <figcaption>
        <span class="map-kicker">A² / THE TAXONOMY</span>
        <h3>Two axes, one record.</h3>
        <p>Activities ask when an obligation is designed, verified, and revisited. Assets ask what must hold and what may change. The dashed return is re-generalization: the contract itself is reopened.</p>
        <div class="map-links"><a class="button button-ghost" href="assets/a2/taxonomy-a2.svg">Open the full map <span aria-hidden="true">↗</span></a><a class="text-link" href="assets/a2/taxonomy-a2.pdf" download>Download PDF <span aria-hidden="true">↓</span></a></div>
      </figcaption>
    </figure>
    <div class="inventory-line"><div class="stat"><strong>52</strong><span>candidate records</span></div><div class="stat"><strong>05</strong><span>source families</span></div><div class="stat"><strong>03</strong><span>activity coordinates</span></div><small>Inventory size, not a prevalence claim.</small></div>
  </section>

  <section class="lens-section" aria-labelledby="lens-title">
    <div class="lens-head"><div class="section-index">A² / THE LENS</div><h2 id="lens-title">Activities × Assets</h2><p>An engineering record gives a design pattern its operational shape. The A² lens asks <strong>when</strong> an obligation is designed, verified, and revisited—and <strong>what</strong> must remain stable while implementations change.</p></div>
    <div class="a2-matrix" role="img" aria-label="A two-by-three matrix: protected contract and permitted variation across design, verification, and evolution activities.">
      <div class="a2-corner"><span>A²</span><small>record lens</small></div>
      <div class="a2-col"><b>A1</b><span>Design</span></div>
      <div class="a2-col"><b>A2</b><span>Verify</span></div>
      <div class="a2-col"><b>A3</b><span>Evolve</span></div>
      <div class="a2-row"><b>Protected contract</b><span>What must hold</span></div>
      <div class="a2-cell"><strong>Declare</strong> authority, state, and acceptance</div>
      <div class="a2-cell"><strong>Exercise</strong> the violation path</div>
      <div class="a2-cell"><strong>Re-generalize</strong> when the seam fails</div>
      <div class="a2-row"><b>Permitted variation</b><span>What may change</span></div>
      <div class="a2-cell"><strong>Admit</strong> adapters, policies, providers</div>
      <div class="a2-cell"><strong>Vary</strong> tests and diagnostics</div>
      <div class="a2-cell"><strong>Move</strong> the mechanism without losing the contract</div>
    </div>
  </section>

  <section class="family-section" aria-labelledby="family-title"><div class="section-index">05 / SOURCE FAMILIES</div><h2 id="family-title" class="visually-hidden">Five source families</h2><div class="family-rules">{family_rules}</div><p class="section-footnote">Families record provenance, not another taxonomy axis. E records are research mechanisms, not claims of independently established recurring patterns.</p></section>

  <section class="catalog-section" id="catalog" aria-labelledby="catalog-title">
    <div class="catalog-heading"><div><span class="section-index">INDEX / 001—052</span><h2 id="catalog-title">Pattern catalog</h2></div><p>Search by responsibility, mechanism, or join point. Filter without losing the underlying record.</p></div>
    <form class="filters" id="filters" role="search" aria-label="Filter pattern catalog">
      <div class="search-field"><label for="pattern-search">Search the field guide</label><input id="pattern-search" name="q" type="search" placeholder="Try ‘sandbox’, ‘state’, or ‘stop’…" autocomplete="off" spellcheck="false"><span aria-hidden="true">⌕</span></div>
      <div class="select-field"><label for="family-filter">Source family</label><select id="family-filter" name="family"><option value="all">All five families</option>{family_options}</select></div>
      <div class="select-field"><label for="activity-filter">A² activity</label><select id="activity-filter" name="activity"><option value="all">All activities</option>{activity_options}</select></div>
      <div class="select-field"><label for="evidence-filter">Evidence status</label><select id="evidence-filter" name="evidence"><option value="all">Any evidence status</option><option value="source_located">Source-located exemplar</option><option value="specification_only">Specification only</option><option value="current_cue">Current retrieval cue</option><option value="no_current_cue">No current retrieval cue</option></select></div>
      <button class="reset-button" id="reset-filters" type="button">Reset</button>
    </form>
    <div class="results-meta"><p aria-live="polite">Showing <strong id="result-count">52</strong> of 52 records</p><p><span class="legend-dot"></span> Source anchors are exemplars, not population estimates.</p></div>
    <div class="pattern-index" id="pattern-index">{rows}</div>
    <div class="empty-state" id="empty-state" hidden><span>∅</span><h3>No records at this intersection.</h3><p>Try a broader term or clear one of the filters. An empty filtered view says nothing about implementations in repositories.</p><button class="button button-primary" type="button" data-reset-filters>Show all 52 records</button></div>
    <noscript><p class="noscript-note">Search and filters require JavaScript. All 52 records remain browsable above without it.</p></noscript>
  </section>

  <aside class="evidence-banner" id="evidence-key"><span class="section-index">READ WITH CARE</span><h2>A cue is a place to look,<br>not a pattern confirmed.</h2><div><p><strong>Proposed specification.</strong> Pointcuts and contracts define what a conforming mechanism would do.</p><p><strong>Exploratory retrieval cue.</strong> A regex or structural match retrieves candidate locations. Any-evidence coverage is not confirmed prevalence.</p><p><strong>Source-located exemplar.</strong> A curator identified a concrete implementation anchor. It does not certify every contract field.</p><p><strong>Human / AI review.</strong> Study annotations are AI-assisted and bounded; independent human validation remains open.</p></div><a class="text-link" href="method.html#evidence-key">Full evidence key and limitations <span aria-hidden="true">↗</span></a></aside>
</main>"""
    return shell("POHE — Pattern-Oriented Harness Engineering: Design Patterns when OOD meets Agentic AI", "An engineering field guide to 52 candidate patterns for agent harnesses: UML class views, pointcuts, contracts, variation, prompt and code design sketches, evidence, and lifecycle.", body, current="catalog")


def anchor_html(anchor: dict) -> str:
    if anchor["kind"] == "external":
        return f"""<div class="source-anchor"><span class="anchor-kind">Paper anchor</span><a href="{esc(anchor['url'])}">{esc(anchor['label'])} <span aria-hidden="true">↗</span></a><p>{esc(anchor['note'])}</p></div>"""
    implementation = esc(anchor["implementation"])
    support = ""
    if anchor.get("support"):
        support = f"""<div class="support-line"><span>Supporting surface</span><a href="{esc(anchor['support_url'])}"><code>{esc(anchor['support'])}</code></a></div>"""
    return f"""<div class="source-anchor"><span class="anchor-kind">Canonical source anchor</span><a class="repo-name" href="{esc(anchor['url'])}">{esc(anchor['repo_slug'])} <span aria-hidden="true">↗</span></a><code class="commit">{esc(anchor['commit_sha'][:12])}</code><a class="locator" href="{esc(anchor['url'])}"><code>{implementation}</code></a>{support}<p>{esc(anchor['note'])}</p></div>"""



def example_section(p: dict) -> str:
    example = EXAMPLES[p["id"]]
    prompt = esc(example["prompt"])
    code = esc(example["code"])
    note = esc(example["note"])
    prompt_id = f"prompt-{p['id']}"
    code_id = f"code-{p['id']}"
    return f"""
  <section class="record-section prompt-code-section" id="prompt-code"><div class="record-section-label"><span>06</span><h2>Prompt + code design</h2><p>An illustrative prompt and a small design sketch for the proposed contract. Names and APIs are invented; this is not a repository excerpt.</p></div>
    <div class="design-grid">
      <article class="design-card"><div class="design-card-head"><span>PROMPT SKETCH</span><button class="copy-button" type="button" data-copy="{prompt_id}">Copy</button></div><pre class="prompt-block" id="{prompt_id}"><code>{prompt}</code></pre></article>
      <article class="design-card"><div class="design-card-head"><span>CODE DESIGN / PYTHON</span><button class="copy-button" type="button" data-copy="{code_id}">Copy</button></div><pre class="code-block" id="{code_id}"><code>{code}</code></pre></article>
    </div>
    <p class="design-note"><strong>Illustrative design sketch.</strong> {note} This example is a teaching aid, not implementation evidence or a conformance claim.</p>
  </section>"""


def repo_files_html(files: list[dict]) -> str:
    if not files:
        return (
            '<div class="repo-files-empty"><strong>No repository file was retrieved for this record.</strong>'
            "<p>The frozen panel returned no cue realization, so the record remains specification-only. "
            "No repository link is invented to fill the gap.</p></div>"
        )
    rows = []
    for index, item in enumerate(files, 1):
        locator = esc(item["path"])
        if item.get("line"):
            locator += f":{item['line']}"
        tag = "CANONICAL SOURCE" if item["kind"] == "canonical source" else "RETRIEVAL CUE"
        label = f"{item['repo']}: {item['path']}" + (f" line {item['line']}" if item.get("line") else "")
        rows.append(
            f'<a class="repo-file" href="{esc(item["url"])}" target="_blank" rel="noreferrer" '
            f'aria-label="{esc(label)} (opens in a new tab)">'
            f'<span class="repo-file-index">{index:02d}</span>'
            f'<span class="repo-file-main"><strong>{esc(item["repo"])}</strong><code>{locator}</code></span>'
            f'<span class="repo-file-kind">{tag}</span><span class="repo-file-arrow" aria-hidden="true">↗</span></a>'
        )
    return "".join(rows)


def render_detail(p: dict, previous_id: str, next_id: str) -> str:
    activities = "".join(f'<li><b>{a}</b><span>{esc(ACTIVITIES[a])}</span></li>' for a in p["activities"])
    pointcut = "".join(f'<div><dt>{label}</dt><dd>{esc(p["pointcut"][key])}</dd></div>' for key, label in (("context", "Context"), ("trigger", "Trigger"), ("structure", "Structure"), ("effect", "Effect")))
    contracts = "".join(f'<div><dt>{label}</dt><dd>{esc(p[key])}</dd></div>' for key, label in (("requires", "Requires"), ("ensures", "Ensures"), ("invariant", "Invariant"), ("violation", "Violation")))
    evidence = p["evidence"]
    if evidence["status"] == "source_located":
        status = "Source-located exemplar"
        evidence_note = "A concrete source anchor is available for this proposed record. It is one exemplar, not evidence that all repositories—or every contract field—conform."
    else:
        status = "Specification only"
        evidence_note = "No official executable implementation was located in the supplied study. The paper anchor motivates the record; it is not an implementation claim."
    anchors = "".join(anchor_html(a) for a in p["anchors"])
    current = evidence["current_cue_repositories"]
    coverage = evidence["family_observed"]
    family_total = evidence["family_total"]
    percent = round(100 * evidence["family_coverage"], 1)
    regex = esc(p["retrieval_cue"]["regex"])
    body = f"""
<main id="main-content" class="record-page" data-family="{p['family']}">
  <div class="record-breadcrumb"><a href="../../#catalog">Catalog</a><span>/</span><span>{p['family']} family</span><span>/</span><span>{p['id']}</span></div>
  <header class="record-header">
    <div class="record-number" aria-hidden="true">{p['id']}</div>
    <div class="record-title"><div class="record-labels"><span>Proposed specification</span><span>{esc(status)}</span></div><h1>{esc(p['name'])}</h1><p>{esc(p['problem'])}</p></div>
    <div class="record-stamp"><span>JOIN POINT</span><code>{esc(p['join_point'])}</code><span>RECORD STATUS</span><strong>Candidate · v{esc(p['codebook_version'])}</strong></div>
  </header>

  <section class="record-section uml-section" id="uml-view"><div class="record-section-label"><span>01</span><h2>UML class view</h2><p>The proposed contract drawn as participant roles, received calls, and numbered dependencies.</p></div><figure class="interaction-figure"><a href="../../{p['class_svg']}" aria-label="Open full-size UML class view for {p['id']}"><img src="../../{p['class_svg']}" alt="UML class view for {esc(p['name'])}, showing participant roles, received calls, and analytical dependencies" loading="lazy"></a><figcaption><span>FIG. {p['id']} / UML CLASS VIEW</span><div class="figure-links"><a href="../../{p['class_svg']}">Open full SVG <span aria-hidden="true">↗</span></a><a class="download-link" href="../../{p['diagram_pdf']}" download>Download PDF <span aria-hidden="true">↓</span></a></div></figcaption></figure></section>

  <section class="record-section interaction-section" id="interactions"><div class="record-section-label"><span>02</span><h2>Object interactions</h2><p>The same roles and calls as a class collaboration and a numbered message sequence.</p></div><figure class="interaction-figure"><a href="../../{p['interaction_svg']}" aria-label="Open full-size object interaction diagram for {p['id']}"><img src="../../{p['interaction_svg']}" alt="Object interaction diagram for {esc(p['name'])}, showing role collaboration and a numbered message sequence" loading="lazy"></a><figcaption><span>FIG. {p['id']} / OBJECT INTERACTIONS</span><div class="figure-links"><a href="../../{p['interaction_svg']}">Open full SVG <span aria-hidden="true">↗</span></a><a class="download-link" href="../../{p['interaction_pdf']}" download>Download PDF <span aria-hidden="true">↓</span></a></div></figcaption></figure></section>

  <nav class="record-toc" aria-label="On this page"><span>On this record</span><a href="#uml-view">UML view</a><a href="#interactions">Object interactions</a><a href="#pointcut">Pointcut</a><a href="#contract">Contract</a><a href="#variation">Variation</a><a href="#prompt-code">Prompt + code</a><a href="#repo-files">Repository files</a><a href="#evidence">Evidence</a></nav>

  <section class="record-section pointcut-section" id="pointcut"><div class="record-section-label"><span>03</span><h2>Pointcut</h2><p>Where the mechanism applies. All four dimensions belong to the proposed match, not just its vocabulary.</p></div><dl class="pointcut-grid">{pointcut}</dl></section>

  <section class="record-section contract-section" id="contract"><div class="record-section-label"><span>04</span><h2>Protected contract</h2><p>The obligation that clients, operators, and auditors should be able to rely on.</p></div><dl class="contract-list">{contracts}</dl><div class="negative-control"><h3>Negative control</h3><p>{esc(p['negative_control'])}</p></div></section>

  <section class="record-section variation-section" id="variation"><div class="record-section-label"><span>05</span><h2>Variation & lifecycle</h2><p>The hot spot is admitted only where the protected semantics survive.</p></div><div class="variation-copy"><div><h3>Permitted variation</h3><p>{esc(p['variation'])}</p></div><div><h3>Test obligation</h3><p>{esc(p['test_obligation'])}</p></div><div><h3>Evolution question</h3><p>{esc(p['evolution_question'])}</p></div></div><aside class="a2-coordinates"><h3>A² activity coordinates</h3><ul>{activities}</ul><p>One record may carry multiple activity coordinates. The five source families do not add an axis.</p></aside></section>



{example_section(p)}

  <section class="record-section repo-files-section" id="repo-files"><div class="record-section-label"><span>07</span><h2>Repository files</h2><p>Up to five public files retrieved by the frozen cue and pinned to the audited commit. A match is a place to inspect, not a confirmed implementation.</p></div><div class="repo-files">{repo_files_html(p['repo_files'])}</div></section>

  <section class="record-section evidence-section" id="evidence"><div class="record-section-label"><span>08</span><h2>Evidence & provenance</h2><p>Each layer answers a different question. Do not substitute retrieval for review.</p></div><div class="evidence-content"><div class="evidence-status"><span class="status-mark"></span><h3>{esc(status)}</h3><p>{esc(evidence_note)}</p><p class="review-note"><strong>Review boundary:</strong> this candidate and its specification come from an AI-assisted study. Independent human validation remains open.</p></div><div class="coverage-figure"><span>ANY-EVIDENCE FAMILY COVERAGE</span><strong>{coverage}<i>/{family_total}</i></strong><div class="coverage-bar" aria-hidden="true"><i style="width:{percent}%"></i></div><p>{percent}% of repository families in the frozen panel have at least one current cue, historical cue, or canonical source layer. <strong>This is not confirmed prevalence.</strong></p><small>Current lexical-cue repositories: {current} / {evidence['repository_total']}</small></div></div><div class="anchors">{anchors}</div><details class="retrieval-cue"><summary>Exploratory retrieval cue <span>Regex / v{esc(p['retrieval_cue']['version'])}</span></summary><div><code>{regex}</code><p>This expression is a discovery instrument only. A match is a retrieval cue—not a confirmed implementation, pointcut match, or contract proof.</p></div></details></section>

  <nav class="record-pagination" aria-label="Adjacent pattern records"><a class="previous-record" href="../{previous_id}/"><span>← Previous record</span><strong>{previous_id}</strong></a><a href="../../#catalog" class="all-records">All 52</a><a class="next-record" href="../{next_id}/"><span>Next record →</span><strong>{next_id}</strong></a></nav>
</main>"""
    return shell(f"{p['id']} · {p['name']} — POHE", f"{p['id']} {p['name']}: proposed harness pattern pointcut, contract, variation, interaction model, and source evidence.", body, prefix="../../", canonical=f"patterns/{p['id']}/")


def render_method(data: dict) -> str:
    hash_rows = "".join(f"<tr><td><code>{esc(path)}</code></td><td><code class=\"hash\">{esc(digest)}</code></td></tr>" for path, digest in data["source_hashes"].items())
    body = f"""
<main id="main-content" class="method-page">
  <header class="method-hero"><span class="section-index">METHOD / EVIDENCE / REPRODUCIBILITY</span><h1>Claims should carry<br><em>their own boundaries.</em></h1><p>This site is a static rendering of a proposed pattern discipline and an exploratory repository audit. It deliberately separates a useful record from the evidence that supports it.</p><div class="method-actions"><a class="button button-primary" href="assets/paper/pohe-position.pdf">Read the complete paper <span aria-hidden="true">↗</span></a><a class="text-link" href="./#catalog">Return to the catalog</a></div></header>

  <section class="method-section" id="evidence-key"><div class="method-section-number">01</div><div><h2>Evidence key</h2><p class="method-lead">A pattern label, a lexical cue, a source-located mechanism, and a reviewed contract are not interchangeable.</p><div class="evidence-ladder"><div><span>E0 / PROPOSED</span><h3>Pattern specification</h3><p>The context, trigger, structure, effect, contract, variation, test obligation, and negative control define a candidate mechanism. A specification does not assert repository conformance.</p></div><div><span>E1 / RETRIEVAL</span><h3>Exploratory retrieval cue</h3><p>A frozen regular expression or structural matcher finds a place to inspect. A hit is not a confirmed implementation. Coverage counts any available evidence layer and is not a prevalence estimate.</p></div><div><span>E2 / SOURCE</span><h3>Source-located exemplar</h3><p>A repository, immutable commit, and implementation locator identify a concrete example. The atlas holds at most one canonical exemplar per candidate, so it cannot measure cross-repository contract depth.</p></div><div><span>E3 / CONTRACT</span><h3>Executable or contract support</h3><p>Ordering, errors, or boundaries need additional executable or contract evidence. The field guide does not infer E3 from the presence of a source anchor.</p></div></div><aside class="review-boundary"><h3>Human / AI review boundary</h3><p>The study used owner-authorized AI-assisted annotation. Its 200 role-conditioned profiles cover only 16 exact structural candidates and measure one model’s consistency, not independent human agreement. Six pointcuts received majority support, eight were rejected, and two remained unresolved in that bounded sensitivity analysis. Independent human validation remains open.</p></aside></div></section>

  <section class="method-section"><div class="method-section-number">02</div><div><h2>Frozen inputs</h2><p>The rendered catalog uses the supplied candidate manifest, pointcut specification, interaction models, canonical atlas, and any-evidence coverage table. Repository clones, caches, evidence packets, and raw evidence are intentionally excluded from this site.</p><dl class="fact-grid"><div><dt>Inventory</dt><dd>52 records / five source families</dd></div><div><dt>Audit panel</dt><dd>41 repositories / 36 families</dd></div><div><dt>Specification</dt><dd>v{esc(data['spec_version'])}</dd></div><div><dt>Diagram models</dt><dd>v{esc(data['diagram_version'])} / analytical</dd></div><div><dt>Study checkout</dt><dd><code>{esc(data['study_revision'])}</code></dd></div><div><dt>Detector environment</dt><dd><code>PyYAML==6.0.3</code><br><code>pandas==2.3.3</code></dd></div></dl><h3>Input and detector SHA-256</h3><p>These hashes identify the exact local inputs used for this rendering. A hash supplies integrity, not validity.</p><div class="hash-table-wrap"><table class="hash-table"><thead><tr><th>Study-relative file</th><th>SHA-256</th></tr></thead><tbody>{hash_rows}</tbody></table></div></div></section>

  <section class="method-section"><div class="method-section-number">03</div><div><h2>Improvement loop</h2><p class="method-lead">Revise from evidence outward; retain a change only when the claim–evidence link and quality gates hold.</p><ol class="loop-list"><li><b>Register claims.</b> Type each statement as descriptive, exploratory, presentational, or causal.</li><li><b>Attach evidence.</b> Name the frozen artifact and independent unit.</li><li><b>Audit integration.</b> Require both evidence and a visible manuscript link.</li><li><b>Rank gaps.</b> Prioritize inference-changing analysis over decorative summaries.</li><li><b>Compute the smallest sufficient result.</b> Preserve denominators, missing-data semantics, and uncertainty.</li><li><b>Run statistical and manuscript QA.</b> Retain or roll back without weakening claim boundaries.</li></ol></div></section>

  <section class="method-section"><div class="method-section-number">04</div><div><h2>Overlay boundary</h2><p>The layered matcher adds Python AST symbols, multi-language declarations, artifact context, exact-symbol refinement, and source triage to frozen lexical retrieval. It remains a discovery instrument, not an automatic conformance classifier.</p><p>The first broad pass produced 851 overinclusive candidates and was rejected. Exact refinement produced 16 review candidates; eight promoted cells live in a <strong>separate, non-frozen overlay</strong>. The frozen 1,272-cell evidence matrix remains unchanged. Overlay coverage therefore cannot be read as a new field-wide prevalence estimate.</p><p>Historical cue gaps are detector gaps, not evidence of retirement. A source path change is a cue-path event, not automatically an architectural redesign.</p></div></section>

  <section class="method-section"><div class="method-section-number">05</div><div><h2>Reproduce the study</h2><p>Run these commands in a complete companion study checkout with its locked environment. Network access and GitHub authentication are needed only for discovery, freezing, and repository materialization. This static site does not include those repository caches.</p><pre class="command-block"><code>python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
make seed test

# Core frozen pipeline
make final verify

# Empirical and longitudinal extension
make longitudinal

# Corpus-level detector, matrix, statistics, and figures
make cartesian

# Layered discovery and separately reviewed overlay
make layered-overlay
make coverage-funnel</code></pre><h3>Rebuild this field guide</h3><pre class="command-block"><code>python3 scripts/generate_site.py
python3 -I tests/validate_site.py
python3 -m http.server 8000</code></pre><p>The generator uses PyYAML with a stdlib fallback and expects <code>../pattern-mining-study</code> and <code>../POHE_complete/main.pdf</code> by default; <code>--study</code> and <code>--paper</code> override those paths.</p><h3>Source repository</h3><p>The supplied study checkout has no configured public remote. This field guide therefore does not invent an external study-repository URL. Canonical source anchors link directly to the named public implementation repository at the recorded commit. The complete local paper is available as <a href="assets/paper/pohe-position.pdf">the companion PDF</a>.</p></div></section>

  <section class="method-section limitations-section"><div class="method-section-number">06</div><div><h2>Limitations</h2><ul class="limitations-list"><li>The 52 records are a scoped candidate inventory, not 52 disjoint or universally established mechanisms.</li><li>Current cue coverage is descriptive retrieval in a selected frozen panel, <strong>not a prevalence denominator</strong> or confirmed prevalence.</li><li>Locating a source-backed exemplar for 51 of 52 records does not establish frequency, generality, or contract conformance elsewhere. E08 remains specification-only.</li><li>Lexical detectors have false-positive and construction-leakage risks. Exact structural matching and one-model profile coding do not replace independent adjudication.</li><li>A² is a proposed analytical lens, not a validated lifecycle model. Recording a contract does not enforce it.</li><li>H1 and H2 are prospective, design-only studies. No causal performance, safety, cost, or reliability benefit follows from repository association.</li><li>The complete paper PDF is an unpublished, untagged preview, not an accessibility-compliant publication file.</li></ul></div></section>

  <section class="method-section colophon-section" id="colophon"><div class="method-section-number">◇</div><div><h2>Colophon: why this field guide exists</h2><p class="colophon-byline">By Haoyi Xiong</p><p class="method-lead">It continues an unpublished master’s research project on design patterns.</p><p>That project asked what this one still asks: when does a recurring solution become a pattern, and what must a record say before anyone else can use it? The vocabulary here is learned from the Gang of Four’s catalog, Roy T. Fielding’s account of architectural styles in network software, and Douglas C. Schmidt’s writing on distributed-computing patterns and the Pattern-Oriented Software Architecture series.</p><p>Those teachers insisted on the discipline this guide tries to keep: name the join point, state the contract, separate what may vary, and show the evidence. The field guide is dedicated to the research that remained unpublished—and to the readers who can carry the question further.</p><ul class="colophon-links"><li><a href="https://roy.gbiv.com/pubs/dissertation/top.htm">Roy T. Fielding, <em>Architectural Styles and the Design of Network-based Software Architectures</em> (2000)</a></li><li><a href="https://www.dre.vanderbilt.edu/~schmidt/">Douglas C. Schmidt</a> — distributed-computing patterns and the POSA series</li><li>Erich Gamma, Richard Helm, Ralph Johnson, and John Vlissides, <em>Design Patterns: Elements of Reusable Object-Oriented Software</em> (1994)</li></ul></div></section>
</main>"""
    return shell("Method & evidence — POHE", "How the POHE field guide separates proposed specifications, retrieval cues, source exemplars, and review; frozen inputs, hashes, commands, overlays, and limitations.", body, current="method", canonical="method.html")


def load_data(study: Path) -> dict:
    candidates = list(csv.DictReader((study / "data/manifests/candidates.csv").open(encoding="utf-8", newline="")))
    spec_doc = yaml_load((study / "protocol/harness_pattern_specification.yaml").read_text(encoding="utf-8"))
    diagram_doc = yaml_load((study / "protocol/pattern_diagram_models.yaml").read_text(encoding="utf-8"))
    detector_doc = yaml_load((study / "protocol/detector_queries.yaml").read_text(encoding="utf-8"))
    specs = {p["id"]: p for p in spec_doc["patterns"]}
    diagrams = diagram_doc["patterns"]
    detector = detector_doc["candidates"]
    atlas = {row["candidate_id"]: row for row in csv.DictReader((study / "reports/full_catalog/pattern_instance_atlas.csv").open(encoding="utf-8", newline=""))}
    coverage = {row["candidate_id"]: row for row in csv.DictReader((study / "data/statistics/pattern_coverage.csv").open(encoding="utf-8", newline=""))}
    realizations: dict[str, list[dict]] = defaultdict(list)
    for row in csv.DictReader((study / "data/derived/pattern_repo_realizations.csv").open(encoding="utf-8", newline="")):
        realizations[row["candidate_id"]].append(row)
    if set(specs) != set(EXPECTED_IDS) or set(diagrams) != set(EXPECTED_IDS):
        raise ValueError("Source protocols do not contain the expected 52 records")
    records = []
    for candidate in candidates:
        pid = candidate["candidate_id"]
        spec = specs[pid]
        evidence_row = atlas[pid]
        coverage_row = coverage[pid]
        activities = candidate["paper_focus"].split("/")
        family = pid[0]
        if evidence_row["status"] == "found":
            status = "source_located"
            anchor = {
                "kind": "source", "repo_slug": evidence_row["repo_slug"],
                "commit_sha": evidence_row["commit_sha"], "family_id": evidence_row["family_id"],
                "implementation": evidence_row["implementation"], "support": evidence_row["support"],
                "note": evidence_row["note"], "url": source_url(evidence_row["repo_slug"], evidence_row["commit_sha"], evidence_row["implementation"]),
                "support_url": source_url(evidence_row["repo_slug"], evidence_row["commit_sha"], evidence_row["support"]) if evidence_row["support"] else "",
            }
            anchors = [anchor]
        else:
            status = "specification_only"
            anchors = [{"kind": "external", "label": "AdaRSI paper (arXiv:2610.20474)", "url": evidence_row["external_url"], "note": evidence_row["note"]}]
        record = {
            "id": pid, "name": spec["name"], "family": family,
            "family_name": FAMILIES[family][0], "codebook_version": candidate["codebook_version"],
            "activities": activities, "activity_names": [ACTIVITIES[a] for a in activities],
            "problem": candidate["problem_and_purpose"], "join_point": spec["join_point"],
            "pointcut": spec["pointcut"], "requires": spec["requires"], "ensures": spec["ensures"],
            "invariant": spec["invariant"], "violation": spec["violation"], "variation": spec["variation"],
            "negative_control": spec["negative_control"], "test_obligation": spec["test_obligation"],
            "evolution_question": spec["evolution_question"], "provenance_class": candidate["provenance_class"],
            "provenance_references": candidate["provenance_references"], "verification_status": candidate["verification_status"],
            "evidence": {
                "status": status, "repository_observed": int(coverage_row["repository_observed"]),
                "repository_total": int(coverage_row["repository_total"]),
                "family_observed": int(coverage_row["family_observed"]), "family_total": int(coverage_row["family_total"]),
                "family_coverage": float(coverage_row["family_coverage"]),
                "current_cue_repositories": int(coverage_row["current_cue_repositories"]),
                "historical_cue_repositories": int(coverage_row["historical_cue_repositories"]),
                "coverage_meaning": "Any current cue, historical cue, or canonical source layer; not confirmed prevalence.",
            },
            "anchors": anchors, "repo_files": realization_files(anchors, realizations.get(pid, [])),
            "interactions": diagrams[pid]["interactions"],
            "retrieval_cue": {"regex": detector[pid]["regex"], "version": detector_doc["version"], "frozen_at": detector_doc["frozen_at"], "role": "exploratory_retrieval_only"},
            "diagram_svg": f"assets/diagrams/{pid}.svg", "diagram_pdf": f"assets/diagrams/{pid}.pdf",
            "class_svg": f"assets/diagrams/{pid}-class.svg",
            "interaction_svg": f"assets/interactions/{pid}.svg", "interaction_pdf": f"assets/interactions/{pid}.pdf",
            "url": f"patterns/{pid}/",
        }
        records.append(record)
    records.sort(key=lambda p: EXPECTED_IDS.index(p["id"]))
    hash_files = [
        "data/manifests/candidates.csv", "protocol/harness_pattern_specification.yaml",
        "protocol/pattern_diagram_models.yaml", "protocol/detector_queries.yaml",
        "reports/full_catalog/pattern_instance_atlas.csv", "data/statistics/pattern_coverage.csv",
        "data/derived/pattern_repo_realizations.csv",
        "data/manifests/current_41_repositories.csv", "environment/requirements.lock",
        "src/detectors/run_candidate_queries.py", "src/detectors/layered_pattern_matcher.py",
    ]
    try:
        revision = subprocess.run(["git", "-C", str(study), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        revision = "unknown"
    return {
        "schema_version": "1.0.0", "title": "Pattern-Oriented Harness Engineering field guide",
        "record_count": len(records), "spec_version": spec_doc["version"], "diagram_version": diagram_doc["version"],
        "study_revision": revision, "source_hashes": {path: sha256(study / path) for path in hash_files},
        "patterns": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=ROOT.parent / "pattern-mining-study")
    parser.add_argument("--paper", type=Path, default=ROOT.parent / "POHE_complete/main.pdf")
    args = parser.parse_args()
    study = args.study.resolve()
    data = load_data(study)
    if data["record_count"] != 52 or [p["id"] for p in data["patterns"]] != EXPECTED_IDS:
        raise ValueError("Catalog must contain exactly P01–P29, W01–W07, C01–C04, R01–R02, E01–E10")
    if set(EXAMPLES) != set(EXPECTED_IDS):
        missing = sorted(set(EXPECTED_IDS) - set(EXAMPLES))
        extra = sorted(set(EXAMPLES) - set(EXPECTED_IDS))
        raise ValueError(f"Examples must cover every record; missing={missing}, extra={extra}")
    write_text(ROOT / "data/patterns.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    write_text(ROOT / "index.html", render_index(data["patterns"]))
    write_text(ROOT / "method.html", render_method(data))
    for index, pattern in enumerate(data["patterns"]):
        write_text(ROOT / "patterns" / pattern["id"] / "index.html", render_detail(pattern, EXPECTED_IDS[(index - 1) % 52], EXPECTED_IDS[(index + 1) % 52]))
        for suffix in ("svg", "pdf"):
            source = study / "reports/pattern_diagrams" / suffix / f"{pattern['id']}.{suffix}"
            target = ROOT / "assets/diagrams" / f"{pattern['id']}.{suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or sha256(source) != sha256(target):
                shutil.copyfile(source, target)
        class_source = study / "reports/pattern_diagrams" / "svg" / f"{pattern['id']}-class.svg"
        class_target = ROOT / "assets/diagrams" / f"{pattern['id']}-class.svg"
        if not class_target.exists() or sha256(class_source) != sha256(class_target):
            shutil.copyfile(class_source, class_target)
        for suffix in ("svg", "pdf"):
            source = study / "reports/pattern_interactions" / suffix / f"{pattern['id']}.{suffix}"
            target = ROOT / "assets/interactions" / f"{pattern['id']}.{suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or sha256(source) != sha256(target):
                shutil.copyfile(source, target)
    paper_target = ROOT / "assets/paper/pohe-position.pdf"
    paper_target.parent.mkdir(parents=True, exist_ok=True)
    if not paper_target.exists() or sha256(args.paper) != sha256(paper_target):
        shutil.copyfile(args.paper, paper_target)
    (ROOT / ".nojekyll").touch()
    print(f"Generated {data['record_count']} records, 52 detail pages, and 104 diagram assets in {ROOT}")


if __name__ == "__main__":
    main()
