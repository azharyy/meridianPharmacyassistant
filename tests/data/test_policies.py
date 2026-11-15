"""The four policy pages: a title, a heading per topic, and anchors that sources can cite.

A section's anchor is its heading lowercased, with every run of other characters turned into a
hyphen: "Delivery area" is policies/delivery.md#delivery-area. Issue 5's retrieval uses the
same rule.
"""

import re
from pathlib import Path

import pytest

from contracts.chat import SOURCE_ID_PATTERN

POLICIES = Path(__file__).resolve().parents[2] / "data" / "policies"
PAGES = ["returns.md", "delivery.md", "privacy.md", "pharmacist-services.md"]


def anchor(heading: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")


def topics(page: str) -> list[tuple[str, str]]:
    """Each `## ` heading on a page and the text under it."""
    text = (POLICIES / page).read_text(encoding="utf-8")
    sections = re.split(r"(?m)^## ", text)[1:]
    return [
        (heading.strip(), body.strip())
        for heading, _, body in (s.partition("\n") for s in sections)
    ]


def test_the_four_pages_and_nothing_else():
    assert sorted(path.name for path in POLICIES.glob("*.md")) == sorted(PAGES)


@pytest.mark.parametrize("page", PAGES)
def test_each_page_has_a_title_and_a_heading_per_topic(page):
    assert (POLICIES / page).read_text(encoding="utf-8").startswith("# ")
    sections = topics(page)
    assert len(sections) >= 3
    for heading, body in sections:
        assert body, heading
        assert re.fullmatch(SOURCE_ID_PATTERN, f"policies/{page}#{anchor(heading)}")
    assert len({anchor(heading) for heading, _ in sections}) == len(sections)


def test_delivery_covers_the_area_the_fees_and_the_times():
    headings = [heading for heading, _ in topics("delivery.md")]
    assert {"Delivery area", "Delivery fees", "Delivery times"} <= set(headings)
