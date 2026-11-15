"""Match product identifiers, ingredient names and aliases before keyword search."""

import re
from collections.abc import Mapping

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
