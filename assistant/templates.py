"""Hold every reply template: the wording that frames record text and API results.

Fixed replies live in assistant/policy.py. Text a template frames is copied word for word.
"""

from contracts.taxonomy import LabelSection

SECTION_TITLES = {
    LabelSection.ACTIVE_INGREDIENTS: "Active ingredients",
    LabelSection.USES: "Uses",
    LabelSection.WARNINGS: "Warnings",
    LabelSection.DIRECTIONS: "Directions",
}
# The title of a label section's source chip, such as "Meridian All Day Allergy: Directions".
LABEL_SOURCE_TITLE = "{name}: {section}"
