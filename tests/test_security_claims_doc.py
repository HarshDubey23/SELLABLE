"""The security claims table must reference things that exist.

`docs/architecture/security-claims.md` maps each claim to a code path and
a test. A reviewer who finds one dead reference in that table reasonably
stops trusting the whole document — and the previous version had ten,
pointing at test files that had been renamed or never existed.

So the table is parsed and resolved here. If a file moves, this fails.
"""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "architecture" / "security-claims.md"

ROW = re.compile(r"^\|\s*(?P<claim>[^|]+?)\s*\|\s*`(?P<code>[^`]+)`\s*\|\s*`(?P<test>[^`]+)`\s*\|\s*$")


def rows() -> list[tuple[str, str, str]]:
    found = []
    for line in DOC.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line)
        if m and not m.group("claim").startswith("---"):
            found.append((m.group("claim"), m.group("code"), m.group("test")))
    assert found, "no claim rows parsed — has the table format changed?"
    return found


def test_the_table_is_not_empty():
    assert len(rows()) >= 30, "the claims table looks truncated"


@pytest.mark.parametrize("claim,code,test", rows(),
                         ids=lambda v: v[:40] if isinstance(v, str) else v)
def test_every_referenced_path_exists(claim, code, test):
    assert (REPO / code).exists(), f"{claim!r} points at a missing path: {code}"
    assert (REPO / test).exists(), f"{claim!r} points at a missing test: {test}"


def test_no_claim_references_an_archived_path():
    text = DOC.read_text(encoding="utf-8")
    assert "docs/log/" not in text, "references a path that moved to docs/archive"
    assert "docs/final/" not in text, "references a path that moved to docs/archive"


def test_the_document_states_what_it_does_not_claim():
    """An evidence table without limitations reads as marketing."""
    text = DOC.read_text(encoding="utf-8")
    assert "What is deliberately not claimed" in text
    for required in ("tamper-", "custody", "Rate limiting", "Clock skew"):
        assert required in text, f"missing limitation: {required}"
