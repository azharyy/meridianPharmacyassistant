"""Fetch public OTC label samples from openFDA into catalog/raw/: what `make fetch-labels` runs.

For each ingredient it asks for OTC labels, newest first, reading up to two pages of 100, and
keeps up to four that have all four sections and pass the rules in scripts/label_text.py. Each
kept label is saved as fetched, as catalog/raw/<set_id>.json, after the folder's old labels are
removed; its set ID and date (effective_time) are inside. It pauses between requests. It needs
the network: run it once, then commit catalog/raw/.
"""

import json
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from scripts.label_text import problems

API = "https://api.fda.gov/drug/label.json"
RAW = Path(__file__).resolve().parents[1] / "catalog" / "raw"
KEEP_PER_INGREDIENT = 4
PAGES = 2
PAGE_SIZE = 100
INGREDIENTS = {
    "allergy": ["cetirizine", "loratadine", "fexofenadine", "levocetirizine", "chlorpheniramine"],
    "pain and fever": ["acetaminophen", "ibuprofen", "naproxen", "aspirin"],
    "cough and cold": ["dextromethorphan", "guaifenesin", "phenylephrine", "oxymetazoline"],
    "digestive": [
        "famotidine",
        "omeprazole",
        "loperamide",
        "bismuth subsalicylate",
        "calcium carbonate",
        "simethicone",
    ],
    "skin": ["hydrocortisone", "clotrimazole", "terbinafine", "benzoyl peroxide"],
    "sleep": ["diphenhydramine", "doxylamine"],
    "eye care": ["ketotifen", "tetrahydrozoline", "naphazoline", "carboxymethylcellulose"],
}


def pause() -> None:
    time.sleep(0.5)


def query(ingredient: str, skip: int = 0) -> dict[str, str | int]:
    search = f'openfda.generic_name:"{ingredient}" AND openfda.product_type:"HUMAN OTC DRUG"'
    return {"search": search, "sort": "effective_time:desc", "limit": PAGE_SIZE, "skip": skip}


def usable_labels(http: httpx.Client, ingredient: str, wait: Callable[[], None]) -> list[dict]:
    """Up to four usable labels for one ingredient, newest first, from at most two pages."""
    usable: list[dict] = []
    for page in range(PAGES):
        response = http.get(API, params=query(ingredient, skip=page * PAGE_SIZE))
        wait()
        if response.status_code == 404:  # openFDA's answer when nothing (more) matches
            break
        response.raise_for_status()
        results = response.json()["results"]
        usable += [label for label in results if not problems(label)]
        if len(usable) >= KEEP_PER_INGREDIENT or len(results) < PAGE_SIZE:
            break
    return usable[:KEEP_PER_INGREDIENT]


def fetch(
    http: httpx.Client,
    ingredients: dict[str, list[str]] = INGREDIENTS,
    wait: Callable[[], None] = pause,
) -> dict[str, list[dict]]:
    """Usable labels per ingredient; an empty list when openFDA has none."""
    return {
        ingredient: usable_labels(http, ingredient, wait)
        for names in ingredients.values()
        for ingredient in names
    }


def save(kept: dict[str, list[dict]], folder: Path = RAW) -> list[Path]:
    """Replace the folder's labels with the kept ones."""
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.json"):
        old.unlink()
    paths = []
    for labels in kept.values():
        for label in labels:
            path = folder / f"{label['set_id']}.json"
            body = json.dumps(label, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
            path.write_text(body, encoding="utf-8", newline="\n")
            paths.append(path)
    return paths


def main() -> None:
    with httpx.Client(timeout=60) as http:
        kept = fetch(http)
    paths = save(kept)
    for ingredient, labels in kept.items():
        print(f"{ingredient}: {len(labels)} usable label(s) kept")
    print(f"saved {len(paths)} labels to catalog/raw/")


if __name__ == "__main__":
    main()
