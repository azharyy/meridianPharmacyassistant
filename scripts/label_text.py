"""Turn one openFDA drug label into the catalog's four sections, word for word, or say why not.

Pure functions over a label's JSON as fetched. The fetch uses them to keep only usable labels,
the catalog was built with them, and the tests use them to check every product against its raw
label. Text is only ever cut, never rewritten: whitespace is normalized, a section's own leading
heading is removed, and the warnings are joined from the parts openFDA returns separately.
"""

import re

# Each section of a catalog record and the openFDA field it comes from.
SECTION_FIELDS = {
    "active_ingredients": "active_ingredient",
    "uses": "indications_and_usage",
    "warnings": "warnings",
    "directions": "dosage_and_administration",
}
# The warning fields openFDA returns separately, in Drug Facts order (21 CFR 201.66).
WARNING_FIELDS = (
    "warnings",
    "do_not_use",
    "ask_doctor",
    "ask_doctor_or_pharmacist",
    "when_using",
    "stop_use",
    "pregnancy_or_breast_feeding",
    "keep_out_of_reach_of_children",
)
HEADINGS = {
    "active_ingredients": r"active ingredients?(?:\s*\(s\))?",
    "uses": r"uses?(?:\s*\(s\))?",
    "warnings": r"warnings?",
    "directions": r"directions",
}
INVISIBLE = re.compile("[​‌‍⁠﻿]")  # zero-width characters
# Signs that openFDA put the wrong text in a field: one section running into another.
MISPLACED = {
    "active_ingredients": re.compile(r"(?i)\b(purpose|uses?|warnings?|directions)\b"),
    "uses": re.compile(
        r"(?i)^(stop use|when using|warnings?|directions|do not use|ask a doctor|purpose|"
        r"active ingredient|keep out of reach)|Warnings|Directions|Other information|"
        r"Inactive ingredients"
    ),
    "warnings": re.compile(r"Directions|Other information|Inactive ingredients|Active ingredient"),
    "directions": re.compile(
        r"Directions|Warnings|Other information|Inactive ingredients|Questions"
    ),
}
STRENGTH = re.compile(r"\d")
COMBINATION = re.compile(r",|/|&|\bAND\b|\bWITH\b", re.IGNORECASE)
PHONE = re.compile(r"\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]\d{4}\b|\b1-8\d\d\b")
UNREADABLE = re.compile("[-�]")  # private-use symbol-font glyphs, or broken text
TRADEMARK = re.compile("[®™]")  # ® or ™
CHILDREN = re.compile(r"(?i)\b(child|children|childrens|children's|infant|infants|junior|kids)\b")
# Words that don't make a brand name distinctive: a brand made only of these and the generic
# name ("Loratadine 10mg", "Fexofenadine HCL") is just the ingredient.
FILLER = {
    "hcl",
    "hydrochloride",
    "usp",
    "mg",
    "tablet",
    "tablets",
    "capsule",
    "capsules",
    "softgel",
    "softgels",
}


def normalize(text: str) -> str:
    """Whitespace collapsed to single spaces; zero-width characters count as whitespace."""
    return " ".join(INVISIBLE.sub(" ", text).split())


def field_text(label: dict, field: str) -> str:
    return normalize(" ".join(label.get(field) or []))


def strip_heading(text: str, section: str) -> str:
    """The text without the section's own leading heading, such as "Directions"."""
    match = re.match(rf"(?i)(?:{HEADINGS[section]})(?=[\s:]|$)[\s:]*", text)
    return text[match.end() :] if match else text


def warnings_text(label: dict) -> str:
    """The main warnings, then every subsection they don't already hold, in Drug Facts order."""
    parts: list[str] = []
    for field in WARNING_FIELDS:
        text = field_text(label, field)
        if field == "warnings":
            text = strip_heading(text, "warnings")
        if text and text not in " ".join(parts):
            parts.append(text)
    return " ".join(parts)


def section_text(label: dict, section: str) -> str:
    if section == "warnings":
        return warnings_text(label)
    text = strip_heading(field_text(label, SECTION_FIELDS[section]), section)
    if section == "active_ingredients":  # some labels run straight on into "Purpose"
        text = re.split(r"\s+Purposes?(?=[\s:]|$)", text, maxsplit=1)[0]
    return text


def sections(label: dict) -> dict[str, str]:
    return {section: section_text(label, section) for section in SECTION_FIELDS}


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def real_names(label: dict) -> list[str]:
    """Brand and manufacturer names, leaving out a brand that is only the generic name."""
    fda = label.get("openfda", {})
    generic = {word for name in fda.get("generic_name", []) for word in words(name)}
    names = [*fda.get("brand_name", []), *fda.get("manufacturer_name", [])]
    return [name for name in names if name.strip() and not words(name) - FILLER <= generic]


def misplaced(found: dict[str, str]) -> list[str]:
    """The sections holding another section's text, or an active ingredient with no strength.

    A cross-reference such as "(see Directions)" is part of the text, not a misplaced section.
    """
    wrong = [
        section
        for section, text in found.items()
        if MISPLACED[section].search(re.sub(r"\(see [^)]*\)", "", text))
    ]
    if not STRENGTH.search(found["active_ingredients"]):
        wrong.append("active_ingredients")
    return wrong


def problems(label: dict) -> list[str]:
    """Why a label can't be used in the catalog; an empty list when it can."""
    if not all(label.get(field) for field in SECTION_FIELDS.values()):
        return ["a section is missing"]
    found = sections(label)
    if not all(found.values()):
        return ["a section is empty"]
    text = " ".join(found.values())
    fda = label.get("openfda", {})
    generic = fda.get("generic_name", [])
    checks = {
        "a section holds the wrong text": misplaced(found),
        "a phone number": PHONE.search(text),
        "a symbol-font or broken character": UNREADABLE.search(text),
        "a trademark sign": TRADEMARK.search(text),
        "a brand or manufacturer name": any(n.lower() in text.lower() for n in real_names(label)),
        "more than one active ingredient": len(generic) != 1 or COMBINATION.search(generic[0]),
        "a children's product": CHILDREN.search(" ".join(fda.get("brand_name", []))),
    }
    return [problem for problem, found in checks.items() if found]
