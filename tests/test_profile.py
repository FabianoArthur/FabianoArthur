"""Checks that keep the profile README honest: assets exist, diagrams are
self-contained and accessible, both languages stay in sync, and nothing
private slips into a public repo."""

import hashlib
import re
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
READMES = {"en": ROOT / "README.md", "pt-BR": ROOT / "README.pt-BR.md"}
ASSETS = ROOT / "docs" / "assets"
SVG_NS = "{http://www.w3.org/2000/svg}"

# Names that must never appear here (employer, clients, internal projects),
# stored only as truncated SHA-256 of the lowercased word, so this public
# file does not itself publish them.
FORBIDDEN_WORD_HASHES = {
    "f84f002b2bed908f",
    "d391c380182a890e",
    "ea1ff3a7e368f916",
    "a566bf515eb70f23",
    "eb4ea9f4ce7e68df",
    "76bbbcc43eec8ef3",
    "142102234bd839b6",
}
TEXT_SUFFIXES = {".md", ".svg", ".py", ".yml", ".yaml", ".toml", ".txt", ""}


def read(path):
    return path.read_text(encoding="utf-8")


def local_refs(markdown):
    """Relative paths referenced by markdown links, <img src> and <source srcset>."""
    refs = re.findall(r"\]\(([^)\s]+)\)", markdown)
    refs += re.findall(r'(?:href|src|srcset)="([^"]+)"', markdown)
    return {r.split("#")[0] for r in refs if not re.match(r"[a-z]+:", r) and not r.startswith("#")}


def repo_links(markdown):
    return set(re.findall(r"https://github\.com/FabianoArthur/([A-Za-z0-9._-]+)", markdown))


def tracked_files():
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [ROOT / line for line in out.splitlines() if line]


class ReadmeTests(unittest.TestCase):
    def test_both_readmes_exist(self):
        for path in READMES.values():
            self.assertTrue(path.is_file(), path)

    def test_local_references_exist(self):
        for lang, path in READMES.items():
            for ref in local_refs(read(path)):
                with self.subTest(lang=lang, ref=ref):
                    self.assertTrue((ROOT / ref).exists(), f"{path.name} points to missing {ref}")

    def test_languages_link_each_other(self):
        self.assertIn("README.pt-BR.md", local_refs(read(READMES["en"])))
        self.assertIn("README.md", local_refs(read(READMES["pt-BR"])))

    def test_languages_list_the_same_repos(self):
        en, pt = (repo_links(read(p)) for p in READMES.values())
        self.assertTrue(en, "no repo links found")
        self.assertEqual(en, pt)

    def test_each_language_uses_its_own_diagram(self):
        self.assertIn("how-i-ship-light.svg", read(READMES["en"]))
        self.assertIn("how-i-ship.pt-BR-light.svg", read(READMES["pt-BR"]))

    def test_every_image_has_alt_text(self):
        for lang, path in READMES.items():
            for tag in re.findall(r"<img\b[^>]*>", read(path)):
                with self.subTest(lang=lang, tag=tag[:60]):
                    self.assertRegex(tag, r'alt="[^"]{3,}"')
            for alt in re.findall(r"!\[([^\]]*)\]", read(path)):
                with self.subTest(lang=lang, alt=alt):
                    self.assertTrue(alt.strip(), "markdown image without alt text")


class DiagramTests(unittest.TestCase):
    NAMES = [
        "how-i-ship-light.svg",
        "how-i-ship-dark.svg",
        "how-i-ship.pt-BR-light.svg",
        "how-i-ship.pt-BR-dark.svg",
    ]

    def svg(self, name):
        return read(ASSETS / name)

    def test_all_variants_exist(self):
        for name in self.NAMES:
            self.assertTrue((ASSETS / name).is_file(), name)

    def test_valid_xml_with_title_and_desc(self):
        for name in self.NAMES:
            with self.subTest(name=name):
                root = ET.fromstring(self.svg(name))
                self.assertEqual(root.tag, SVG_NS + "svg")
                self.assertEqual(root.get("role"), "img")
                title = root.find(SVG_NS + "title")
                desc = root.find(SVG_NS + "desc")
                self.assertTrue(title is not None and title.text.strip())
                self.assertTrue(desc is not None and len(desc.text.strip()) > 80)

    def test_animated_with_css_and_respects_reduced_motion(self):
        for name in self.NAMES:
            with self.subTest(name=name):
                svg = self.svg(name)
                self.assertIn("@keyframes", svg)
                self.assertRegex(svg, r"@media\s*\(prefers-reduced-motion:\s*reduce\)")

    def test_self_contained(self):
        for name in self.NAMES:
            with self.subTest(name=name):
                svg = self.svg(name)
                self.assertNotIn("<script", svg)
                self.assertNotIn("@import", svg)
                self.assertNotRegex(svg, r"url\(\s*['\"]?https?:")
                self.assertNotRegex(svg, r'href="https?:')
                self.assertNotIn("<animate", svg, "use CSS keyframes, not SMIL")

    def test_languages_differ(self):
        self.assertNotEqual(self.svg("how-i-ship-dark.svg"), self.svg("how-i-ship.pt-BR-dark.svg"))
        self.assertIn('lang="pt-BR"', self.svg("how-i-ship.pt-BR-dark.svg"))

    def test_committed_svgs_match_generator(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_diagram.py"), "--check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class PublicHygieneTests(unittest.TestCase):
    def test_no_private_names(self):
        for path in tracked_files():
            if path.suffix not in TEXT_SUFFIXES or not path.is_file():
                continue
            words = set(re.findall(r"[a-z0-9]+", read(path).lower()))
            hits = {w for w in words if hashlib.sha256(w.encode()).hexdigest()[:16] in FORBIDDEN_WORD_HASHES}
            with self.subTest(file=path.name):
                self.assertFalse(hits, "private name found")

    def test_no_local_paths(self):
        for path in tracked_files():
            if path.suffix not in TEXT_SUFFIXES or not path.is_file():
                continue
            with self.subTest(file=path.name):
                self.assertNotRegex(read(path), r"/(Users|home)/[a-z]")

    def test_no_email_addresses(self):
        for path in tracked_files():
            if path.suffix not in TEXT_SUFFIXES or not path.is_file():
                continue
            with self.subTest(file=path.name):
                self.assertIsNone(
                    re.search(r"[\w.+-]+@(?!users\.noreply\.github\.com)[\w-]+\.[\w.]+", read(path)),
                )

    def test_license_is_mit(self):
        text = read(ROOT / "LICENSE")
        self.assertIn("MIT License", text)
        self.assertIn("Fabiano Arthur", text)


if __name__ == "__main__":
    unittest.main()
