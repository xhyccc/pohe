#!/usr/bin/env python3
"""Stdlib integrity checks for the generated POHE static site."""
from __future__ import annotations

import html
import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_IDS = (
    [f"P{i:02d}" for i in range(1, 30)]
    + [f"W{i:02d}" for i in range(1, 8)]
    + [f"C{i:02d}" for i in range(1, 5)]
    + [f"R{i:02d}" for i in range(1, 3)]
    + [f"E{i:02d}" for i in range(1, 11)]
)
REQUIRED_PATTERN_FIELDS = {
    "id", "name", "family", "family_name", "activities", "activity_names",
    "problem", "join_point", "pointcut", "requires", "ensures", "invariant",
    "violation", "variation", "negative_control", "test_obligation",
    "evolution_question", "evidence", "anchors", "interactions", "diagram_svg",
    "diagram_pdf", "class_svg", "interaction_svg", "interaction_pdf", "repo_files", "url",
}


class DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []
        self.external_scripts: list[str] = []
        self.ids: set[str] = set()
        self.pattern_rows = 0
        self.has_main = False
        self.has_description = False
        self.has_viewport = False
        self.has_lang = False
        self.has_charset = False

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs_list)
        if attrs.get("id"):
            self.ids.add(attrs["id"] or "")
        if tag == "html" and attrs.get("lang") == "en":
            self.has_lang = True
        if tag == "meta" and attrs.get("charset"):
            self.has_charset = True
        if tag == "meta" and attrs.get("name") == "description" and attrs.get("content"):
            self.has_description = True
        if tag == "meta" and attrs.get("name") == "viewport":
            self.has_viewport = True
        if tag == "main" and attrs.get("id") == "main-content":
            self.has_main = True
        if attrs.get("data-pattern") is not None:
            self.pattern_rows += 1
        for attribute in ("href", "src", "poster"):
            value = attrs.get(attribute)
            if value:
                self.references.append(value)
        if tag == "script" and attrs.get("src", "").startswith(("http://", "https://", "//")):
            self.external_scripts.append(attrs["src"] or "")


def parse_document(path: Path) -> tuple[str, DocumentParser]:
    text = path.read_text(encoding="utf-8")
    parser = DocumentParser()
    parser.feed(text)
    return text, parser


class SiteIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data_path = ROOT / "data" / "patterns.json"
        cls.data = json.loads(cls.data_path.read_text(encoding="utf-8"))
        cls.patterns = cls.data["patterns"]
        cls.by_id = {pattern["id"]: pattern for pattern in cls.patterns}

    def test_exact_catalog_and_record_schema(self) -> None:
        self.assertEqual(len(self.patterns), 52)
        self.assertEqual([p["id"] for p in self.patterns], EXPECTED_IDS)
        for pattern in self.patterns:
            with self.subTest(pattern=pattern.get("id")):
                self.assertTrue(REQUIRED_PATTERN_FIELDS.issubset(pattern))
                self.assertEqual(set(pattern["pointcut"]), {"context", "trigger", "structure", "effect"})
                self.assertTrue(all(pattern["pointcut"].values()))
                self.assertTrue(pattern["interactions"])
                self.assertGreaterEqual(len(pattern["interactions"]), 3)
                self.assertIn(pattern["evidence"]["status"], {"source_located", "specification_only"})
                self.assertEqual(pattern["url"], f"patterns/{pattern['id']}/")

    def test_unique_ids_and_titles(self) -> None:
        ids = [p["id"] for p in self.patterns]
        titles = [p["name"].strip().casefold() for p in self.patterns]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(titles), len(set(titles)))

    def test_all_detail_pages_and_navigation(self) -> None:
        for index, pattern_id in enumerate(EXPECTED_IDS):
            page = ROOT / "patterns" / pattern_id / "index.html"
            with self.subTest(pattern=pattern_id):
                self.assertTrue(page.is_file(), page)
                text, parser = parse_document(page)
                pattern = self.by_id[pattern_id]
                self.assertIn(f"<h1", text)
                self.assertIn(pattern["name"], text)
                self.assertIn("Context", text)
                self.assertIn("Trigger", text)
                self.assertIn("Structure", text)
                self.assertIn("Effect", text)
                self.assertIn("Negative control", text)
                self.assertIn("UML class view", text)
                self.assertIn("Object interactions", text)
                self.assertIn(f'id="interactions"', text)
                self.assertIn(f"assets/interactions/{pattern_id}.svg", text)
                self.assertIn(f"assets/interactions/{pattern_id}.pdf", text)
                self.assertIn("Repository files", text)
                self.assertIn('id="repo-files"', text)
                if pattern["repo_files"]:
                    self.assertIn('class="repo-file"', text)
                    self.assertIn("https://github.com/", text)
                else:
                    self.assertIn("No repository file was retrieved", text)
                self.assertIn("Prompt + code design", text)
                self.assertIn("PROMPT SKETCH", text)
                self.assertIn("CODE DESIGN / PYTHON", text)
                self.assertIn(f'id="prompt-{pattern_id}"', text)
                self.assertIn(f'id="code-{pattern_id}"', text)
                self.assertIn(f'data-copy="prompt-{pattern_id}"', text)
                self.assertIn("not observed traces, repository class declarations", text)
                self.assertIn("retrieval cue", text.lower())
                self.assertIn("download", text.lower())
                self.assertTrue(parser.has_main)
                previous_id = EXPECTED_IDS[(index - 1) % 52]
                next_id = EXPECTED_IDS[(index + 1) % 52]
                self.assertIn(f"../{previous_id}/", text)
                self.assertIn(f"../{next_id}/", text)

    def test_catalog_search_filters_and_empty_state(self) -> None:
        text, parser = parse_document(ROOT / "index.html")
        self.assertEqual(parser.pattern_rows, 52)
        self.assertTrue({"pattern-search", "family-filter", "activity-filter", "evidence-filter", "pattern-index", "empty-state"}.issubset(parser.ids))
        self.assertIn('id="empty-state" hidden', text)
        self.assertIn("52", text)
        self.assertIn("Activities × Assets", text)
        self.assertIn("Pattern-Oriented", text)
        self.assertIn("Harness Engineering", text)
        self.assertIn("Design needs Patterns, when Agentic AI meets OOD", text)
        for family in ("P", "W", "C", "R", "E"):
            self.assertIn(f'value="{family}"', text)
        for activity in ("A1", "A2", "A3"):
            self.assertIn(f'value="{activity}"', text)
        for status in ("source_located", "specification_only", "current_cue", "no_current_cue"):
            self.assertIn(f'value="{status}"', text)
        self.assertIn("coverage is not confirmed prevalence", text.lower())

    def test_page_metadata_and_accessibility_shell(self) -> None:
        pages = [ROOT / "index.html", ROOT / "method.html"] + [ROOT / "patterns" / pid / "index.html" for pid in EXPECTED_IDS]
        for page in pages:
            with self.subTest(page=page.relative_to(ROOT)):
                text, parser = parse_document(page)
                self.assertTrue(parser.has_lang)
                self.assertTrue(parser.has_charset)
                self.assertTrue(parser.has_description)
                self.assertTrue(parser.has_viewport)
                self.assertTrue(parser.has_main)
                self.assertIn('class="skip-link" href="#main-content"', text)
                self.assertIn("<title>", text)
                self.assertEqual(parser.external_scripts, [])
                self.assertIn('id="nav-toggle"', text)
                self.assertIn('aria-expanded="false"', text)
                self.assertIn('href="https://xhyccc.github.io/"', text)

    def test_all_local_html_references_resolve(self) -> None:
        pages = [ROOT / "index.html", ROOT / "method.html"] + [ROOT / "patterns" / pid / "index.html" for pid in EXPECTED_IDS]
        for page in pages:
            _, parser = parse_document(page)
            for reference in parser.references:
                if reference.startswith(("#", "http://", "https://", "mailto:", "data:")):
                    continue
                clean = unquote(urlsplit(reference).path)
                target = (page.parent / clean).resolve()
                with self.subTest(page=page.relative_to(ROOT), reference=reference):
                    self.assertTrue(str(target).startswith(str(ROOT.resolve())), "reference escapes site root")
                    if clean.endswith("/"):
                        target = target / "index.html"
                    self.assertTrue(target.is_file(), f"missing {target}")

    def test_diagram_and_paper_assets(self) -> None:
        paper = ROOT / "assets" / "paper" / "pohe-position.pdf"
        self.assertTrue(paper.is_file())
        self.assertEqual(paper.read_bytes()[:4], b"%PDF")
        for pattern in self.patterns:
            with self.subTest(pattern=pattern["id"]):
                svg = ROOT / pattern["diagram_svg"]
                class_svg = ROOT / pattern["class_svg"]
                pdf = ROOT / pattern["diagram_pdf"]
                interaction_svg = ROOT / pattern["interaction_svg"]
                interaction_pdf = ROOT / pattern["interaction_pdf"]
                self.assertTrue(svg.is_file())
                self.assertTrue(class_svg.is_file())
                self.assertTrue(pdf.is_file())
                self.assertTrue(interaction_svg.is_file())
                self.assertTrue(interaction_pdf.is_file())
                self.assertIn("<svg", svg.read_text(encoding="utf-8")[:2000])
                self.assertIn("<svg", class_svg.read_text(encoding="utf-8")[:2000])
                self.assertIn("<svg", interaction_svg.read_text(encoding="utf-8")[:2000])
                self.assertEqual(pdf.read_bytes()[:4], b"%PDF")
                self.assertEqual(interaction_pdf.read_bytes()[:4], b"%PDF")
                self.assertTrue(all(len(edge) == 4 for edge in pattern["interactions"]))
                if pattern["id"] == "E08":
                    self.assertEqual(pattern["repo_files"], [])
                else:
                    self.assertTrue(1 <= len(pattern["repo_files"]) <= 5)
                for item in pattern["repo_files"]:
                    self.assertRegex(item["url"], r"^https://github\.com/[^/]+/[^/]+/blob/[0-9a-f]{40}/")

    def test_method_and_reproducibility_boundaries(self) -> None:
        text = (ROOT / "method.html").read_text(encoding="utf-8").lower()
        for phrase in (
            "frozen inputs", "sha-256", "improvement loop", "overlay", "limitations",
            "make final verify", "make longitudinal", "make cartesian", "pyyaml==6.0.3",
            "human", "not a prevalence", "source repository",
        ):
            self.assertIn(phrase, text)
        self.assertIn("assets/paper/pohe-position.pdf", text)
        self.assertGreaterEqual(len(self.data.get("source_hashes", {})), 6)
        self.assertRegex(self.data["study_revision"], r"^[0-9a-f]{40}$")

    def test_support_files_and_javascript_wiring(self) -> None:
        for relative in (
            ".nojekyll", ".github/workflows/pages.yml", "README.md",
            "scripts/generate_site.py", "scripts/pattern_examples.py",
            "assets/styles.css", "assets/site.js",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)
        script = (ROOT / "assets/site.js").read_text(encoding="utf-8")
        for token in ("pattern-search", "family-filter", "activity-filter", "evidence-filter", "empty-state", "nav-toggle", "URLSearchParams", "data-copy", "navigator.clipboard"):
            self.assertIn(token, script)
        self.assertNotIn("fetch(", script)
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
        self.assertIn("actions/upload-pages-artifact", workflow)
        self.assertIn("actions/deploy-pages", workflow)
        self.assertIn("path: .", workflow)

    def test_every_record_has_a_prompt_and_code_sketch(self) -> None:
        import sys
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(ROOT / "scripts"))
        from pattern_examples import EXAMPLES

        self.assertEqual(set(EXAMPLES), set(EXPECTED_IDS))
        for pattern_id, example in EXAMPLES.items():
            with self.subTest(pattern=pattern_id):
                self.assertGreaterEqual(len(example["prompt"].split()), 18)
                self.assertGreaterEqual(len(example["code"].splitlines()), 4)
                self.assertTrue(example["note"])
                page = html.unescape((ROOT / "patterns" / pattern_id / "index.html").read_text(encoding="utf-8"))
                self.assertIn(example["note"], page)
                self.assertIn(example["prompt"].splitlines()[0], page)

    def test_hero_a2_map_assets_and_links(self) -> None:
        svg = ROOT / "assets" / "a2" / "taxonomy-a2.svg"
        pdf = ROOT / "assets" / "a2" / "taxonomy-a2.pdf"
        self.assertTrue(svg.is_file(), svg)
        self.assertTrue(pdf.is_file(), pdf)
        self.assertIn("<svg", svg.read_text(encoding="utf-8")[:400])
        self.assertEqual(pdf.read_bytes()[:4], b"%PDF")
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="a2-map"', text)
        self.assertIn('class="hero-map"', text)
        self.assertIn("assets/a2/taxonomy-a2.svg", text)
        self.assertIn("assets/a2/taxonomy-a2.pdf", text)
        self.assertIn("Open the full map", text)
        self.assertIn('href="#a2-map"', text)

    def test_colophon_and_influences(self) -> None:
        text = (ROOT / "method.html").read_text(encoding="utf-8")
        self.assertIn('id="colophon"', text)
        self.assertIn("Colophon", text)
        self.assertIn("By Haoyi Xiong", text)
        self.assertNotIn("Affiliation", text)
        for phrase in (
            "unpublished master’s research project on design patterns",
            "Gang of Four",
            "Roy T. Fielding",
            "Douglas C. Schmidt",
            "Pattern-Oriented Software Architecture",
        ):
            self.assertIn(phrase, text)
        self.assertIn("https://roy.gbiv.com/pubs/dissertation/top.htm", text)
        self.assertIn("https://www.dre.vanderbilt.edu/~schmidt/", text)
        self.assertIn('href="method.html#colophon"', (ROOT / "index.html").read_text(encoding="utf-8"))

    def test_no_raw_evidence_or_cache_material(self) -> None:
        forbidden = [p for p in ROOT.rglob("*") if p.is_file() and (p.suffix in {".jsonl", ".zip"} or "__pycache__" in p.parts)]
        self.assertEqual(forbidden, [])
        all_html = "\n".join(p.read_text(encoding="utf-8") for p in ROOT.rglob("*.html"))
        self.assertNotRegex(all_html, re.compile(r"confirmed\s+(?:implementation|prevalence)\s*[:=]\s*(?:true|100%)", re.I))


if __name__ == "__main__":
    unittest.main(verbosity=2)
