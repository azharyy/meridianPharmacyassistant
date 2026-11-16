"""Match product identifiers, ingredient names and aliases before keyword search."""

import re
from collections.abc import Iterable, Mapping

from contracts.catalog import ProductRecord


def normalize(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text.casefold()).strip()


def phrase(query: str, term: str) -> re.Match[str] | None:
    words = normalize(term).split()
    if not words:
        return None
    pattern = r"\s*".join(re.escape(word) for word in words)
    return re.search(rf"(?<!\w){pattern}(?!\w)", query)


def ingredients(product: ProductRecord) -> set[str]:
    # shortcut: one active ingredient per label; revisit before combination products.
    label = re.sub(r"^\([^)]*\)\s*", "", product.active_ingredients)
    name = re.split(r"\d", label, maxsplit=1)[0]
    name = re.sub(r"\b(?:usp|hcl|hbr|hydrochloride)\b", "", name, flags=re.IGNORECASE)
    name = normalize(name)
    name = re.sub(r" (?:delayed release )?(?:tablet|capsule)s?$", "", name)
    base = re.sub(r"^sodium | (?:sodium|maleate|succinate)$", "", name)
    return {term for term in (name, base) if term}


def alias_terms(query: str, aliases: Mapping[str, str]) -> list[str]:
    return [target for alias, target in aliases.items() if phrase(query, alias)]


def named_products(query: str, products: list[ProductRecord]) -> list[str]:
    mentions = []
    for product in products:
        for term in (product.sku, product.name):
            if first := phrase(query, term):
                mentions.extend(
                    (match.start(), match.end(), product.sku) for match in first.re.finditer(query)
                )
    # A full name such as "Allergy Capsules" takes precedence over its shorter family name.
    specific = [
        mention
        for mention in mentions
        if not any(
            start <= mention[0] and end >= mention[1] and end - start > mention[1] - mention[0]
            for start, end, _ in mentions
        )
    ]
    return [sku for _, _, sku in sorted(specific)]


def product_terms(
    products: list[ProductRecord], aliases: Mapping[str, str]
) -> dict[str, list[str]]:
    terms: dict[str, list[str]] = {}
    for product in products:
        for name in ingredients(product):
            terms.setdefault(name, []).append(product.sku)
    for alias, target in aliases.items():
        terms[normalize(alias)] = [
            product.sku
            for product in products
            if phrase(normalize(product.active_ingredients), target)
        ]
    return terms


def typos(a: str, b: str) -> int:
    """Letters inserted, deleted or replaced, or neighbors swapped, to turn a into b."""
    before, previous = [], list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        row = [i]
        for j, y in enumerate(b, 1):
            cost = min(previous[j] + 1, row[j - 1] + 1, previous[j - 1] + (x != y))
            if i > 1 and j > 1 and x == b[j - 2] and a[i - 2] == y:
                cost = min(cost, before[j - 2] + 1)
            row.append(cost)
        before, previous = previous, row
    return previous[-1]


def respell(query: str, terms: Iterable[str]) -> str:
    """Respell a word one typo from exactly one catalog word of six or more letters (two
    typos from nine or more). Lengths stay within one letter, so look-alike drugs outside
    the catalog, such as desloratadine for loratadine, stay as typed."""
    # shortcut: an English word one typo from a brand ("unison", Unisom) also adds that
    # brand's products to the candidates; check a dictionary first if the eval shows misses.
    known = {word for term in terms for word in term.split() if len(word) >= 6}
    words = query.split()
    for n, word in enumerate(words):
        if word in known:
            continue
        close = [
            term
            for term in known
            if abs(len(word) - len(term)) <= 1 and typos(word, term) <= (2 if len(term) >= 9 else 1)
        ]
        if len(close) == 1:
            words[n] = close[0]
    return " ".join(words)


def exact_products(
    query: str, products: list[ProductRecord], aliases: Mapping[str, str]
) -> list[str]:
    query = normalize(query)
    matched = named_products(query, products)
    groups = sorted(
        (match.start(), -len(term), term, skus)
        for term, skus in product_terms(products, aliases).items()
        if skus and (match := phrase(query, term))
    )
    # Represent each named ingredient/brand before filling the remaining slots with variants.
    for _, _, _, skus in groups:
        if not any(sku in matched for sku in skus):
            matched.append(skus[0])
    matched.extend(sku for _, _, _, skus in groups for sku in skus)
    return list(dict.fromkeys(matched))
