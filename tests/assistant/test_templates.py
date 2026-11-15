"""Every label section has a title, and a label source's title names the product and section."""

from assistant import templates
from contracts.taxonomy import LabelSection


def test_every_label_section_has_a_title():
    assert set(templates.SECTION_TITLES) == set(LabelSection)
    assert all(title.strip() == title and title for title in templates.SECTION_TITLES.values())


def test_a_label_source_title_names_the_product_and_section():
    title = templates.LABEL_SOURCE_TITLE.format(name="Meridian All Day Allergy", section="Uses")
    assert title == "Meridian All Day Allergy: Uses"
