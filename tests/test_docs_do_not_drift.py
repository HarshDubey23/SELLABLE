"""No live document may make a claim the evidence file does not support.

`scripts/verify_readme.py` already does this for the README. It was not
enough: `docs/SUBMISSION_DOSSIER.md` sat one directory away claiming 131
passing tests, "20 out of 20 attacks neutralized", "0% money loss" and
a rupee figure for fraud "prevented" — four claims the README's own guard
bans, in a document a reviewer is at least as likely to open. It has been
archived; this stops the next one.

The rule is narrow on purpose. It does not police prose. It bans a short
list of specific claims that are either false, unmeasured, or were
produced once by a seeded simulation and then quoted as an observation.
Anything under `docs/archive/` is exempt — that directory exists so
superseded documents can be kept without being mistaken for current ones.
"""
from __future__ import annotations

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]

# Documents a reviewer might read as current.
LIVE_DOCS = sorted(REPO.glob("*.md")) + sorted(
    p for p in (REPO / "docs").rglob("*.md")
    if "archive" not in p.relative_to(REPO).parts
)

# (pattern, why it must not appear in a live document)
BANNED = [
    (r"\b131 (passing|passed)", "stale test count; the real one is in truth.json"),
    (r"\b142 (passing|passed)", "stale test count from an earlier build"),
    (r"20 out of 20 attacks", "there are 8 adversarial scenarios, not 20"),
    (r"Attacks Blocked-20", "there are 8 adversarial scenarios, not 20"),
    (r"0% money loss", "not a measured quantity in this repository"),
    (r"Money Loss Rate-0%", "not a measured quantity in this repository"),
    (r"74,?861", "a seeded-simulation figure once quoted as a real loss"),
    (r"\b45\.02\b", "eval AOV figure whose provenance did not survive review"),
    (r"100% (secure|safe|unhackable)", "unfalsifiable security claim"),
    (r"zero vulnerabilit", "unfalsifiable security claim"),
    (r"cheapest on the internet", "an unprovable comparative claim"),
]

# HTML surfaces that no longer exist. A live document telling a reviewer to
# open one of these sends them somewhere that only redirects.
RETIRED_PAGES = [
    "/console", "/attack-ui", "/gateway-ui", "/audit-ui",
    "/audit/timeline", "/market-radar", "/discovery/ui",
]

# A document that tells a presenter NOT to say "100% secure" contains the
# phrase and is doing exactly the right thing. The guard therefore has to
# tell an endorsement from a prohibition: sections whose heading announces
# a list of things to avoid are skipped.
_PROHIBITION_HEADING = re.compile(
    r"^#+\s.*(not to say|never say|do not say|don't say|avoid|banned|"
    r"forbidden|must not)", re.IGNORECASE)


def _claiming_text(markdown: str) -> str:
    """The document minus its own don't-say lists."""
    kept: list[str] = []
    skipping = False
    for line in markdown.splitlines():
        if line.lstrip().startswith("#"):
            skipping = bool(_PROHIBITION_HEADING.match(line.strip()))
        if not skipping:
            kept.append(line)
    return "\n".join(kept)


@pytest.mark.parametrize("doc", LIVE_DOCS, ids=lambda p: str(p.relative_to(REPO)))
def test_no_live_document_makes_a_banned_claim(doc):
    text = _claiming_text(doc.read_text(encoding="utf-8", errors="replace"))
    offences = [
        f"{pattern!r} - {why}"
        for pattern, why in BANNED
        if re.search(pattern, text, re.IGNORECASE)
    ]
    assert offences == [], (
        f"{doc.relative_to(REPO)} makes claims that are not supported:\n  "
        + "\n  ".join(offences)
        + "\n\nEither remove the claim or move the document under docs/archive/.")


@pytest.mark.parametrize("doc", LIVE_DOCS, ids=lambda p: str(p.relative_to(REPO)))
def test_no_live_document_sends_a_reader_to_a_retired_page(doc):
    text = doc.read_text(encoding="utf-8", errors="replace")
    # Only a bare page reference counts, not a path inside apps/ or docs/.
    found = [
        page for page in RETIRED_PAGES
        if re.search(r"(?<![\w/])" + re.escape(page) + r"(?![\w/-])", text)
    ]
    assert found == [], (
        f"{doc.relative_to(REPO)} points a reader at retired pages: {found}. "
        f"They redirect rather than 404, but a current document should name "
        f"where the capability actually lives.")


def test_the_guard_covers_the_documents_that_matter():
    """A guard that silently stops matching files is not a guard."""
    names = {p.name for p in LIVE_DOCS}
    for expected in ("README.md", "WHAT_BROKE.md", "ARCHITECTURE.md"):
        assert expected in names, f"{expected} is no longer being checked"
    assert not any("archive" in p.parts for p in LIVE_DOCS), \
        "archived documents must stay exempt"
    assert len(LIVE_DOCS) >= 10, (
        f"only {len(LIVE_DOCS)} documents matched; the glob has probably "
        f"stopped finding them")


def test_the_prohibition_exemption_is_narrow():
    """The exemption must not become a way to smuggle a claim back in."""
    both = _claiming_text(
        "# Overview\n\nSELLABLE is 100% secure.\n\n"
        "## Things not to say\n\n- 100% secure\n")
    assert "100% secure" in both, \
        "a claim in a normal section must still be caught"

    warning_only = _claiming_text(
        "# Overview\n\nNothing claimed here.\n\n"
        "## Things not to say\n\n- 100% secure\n")
    assert "100% secure" not in warning_only, \
        "a don't-say list must not count as making the claim"
