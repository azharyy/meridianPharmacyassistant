"""Find whole catalog records through an in-memory SQLite section index."""

import json
import re
import sqlite3
from collections.abc import Mapping
from pathlib import Path

from assistant.retrieval.aliases import load_aliases
from assistant.retrieval.exact import alias_terms, exact_products, named_products, normalize, phrase
from contracts.catalog import PolicyRecord, ProductRecord

ROOT = Path(__file__).resolve().parents[2]
SECTIONS = ("active_ingredients", "uses", "warnings", "directions")
Record = ProductRecord | PolicyRecord


def load_records(products_path: Path, policies_dir: Path) -> list[Record]:
    products = json.loads(products_path.read_text(encoding="utf-8"))
    records: list[Record] = [ProductRecord.model_validate(product) for product in products]
    for page in sorted(policies_dir.glob("*.md")):
        for section in re.split(r"(?m)^## ", page.read_text(encoding="utf-8"))[1:]:
            heading, _, body = section.partition("\n")
            anchor = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
            records.append(
                PolicyRecord(
                    source_id=f"policies/{page.name}#{anchor}",
                    title=heading.strip(),
                    text=body.strip(),
                )
            )
    return records


def record_id(record: Record) -> str:
    return record.sku if isinstance(record, ProductRecord) else record.source_id


class SearchIndex:
    """Build once at startup; searches read only and return at most k whole records."""

    def __init__(
        self,
        products_path: Path = ROOT / "catalog" / "products.json",
        policies_dir: Path = ROOT / "data" / "policies",
        *,
        exact_match: bool = True,
        aliases: Mapping[str, str] | None = None,
    ) -> None:
        records = load_records(products_path, policies_dir)
        self.records = {record_id(record): record for record in records}
        self.products = [record for record in records if isinstance(record, ProductRecord)]
        self.exact_match = exact_match
        self.aliases = (
            load_aliases(ROOT / "catalog" / "aliases.yaml") if aliases is None else aliases
        )
        # A brand alias reaches its products in the exact stage; keyword search for its
        # ingredient would only crowd out the rest of the question (a returns policy, say).
        self.label_aliases = {
            alias: target
            for alias, target in self.aliases.items()
            if not any(phrase(normalize(p.active_ingredients), target) for p in self.products)
        }
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.execute(
            "CREATE VIRTUAL TABLE sections USING fts5(record_id UNINDEXED, title, text)"
        )
        for record in records:
            if isinstance(record, ProductRecord):
                title = f"{record.sku} {record.name}"
                texts = [getattr(record, section) for section in SECTIONS]
            else:
                title = f"{record.source_id.split('#')[0]} {record.title}"
                texts = [record.text]
            self.connection.executemany(
                "INSERT INTO sections VALUES (?, ?, ?)",
                [(record_id(record), title, text) for text in texts],
            )
        self.connection.commit()

    def search(self, query: str, k: int) -> list[Record]:
        ids = []
        if self.exact_match:
            ids.extend(exact_products(query, self.products, self.aliases))
            targets = alias_terms(normalize(query), self.label_aliases)
            ids.extend(self.keyword_ids(" ".join(targets)))
        ids.extend(self.keyword_ids(query))
        return [self.records[key] for key in dict.fromkeys(ids)][:k]

    def named(self, query: str) -> ProductRecord | None:
        """One explicit product, or an unambiguous ingredient/alias; never guess a variant."""
        skus = set(named_products(normalize(query), self.products))
        if not skus:
            skus = set(exact_products(query, self.products, self.aliases))
        return self.records[next(iter(skus))] if len(skus) == 1 else None

    def keyword_ids(self, query: str) -> list[str]:
        tokens = list(dict.fromkeys(re.findall(r"\w+", query.casefold(), flags=re.UNICODE)))
        if not tokens:
            return []
        match = " OR ".join(f'"{token}"' for token in tokens)
        rows = self.connection.execute(
            "SELECT record_id FROM sections WHERE sections MATCH ? ORDER BY bm25(sections), rowid",
            (match,),
        )
        return list(dict.fromkeys(row[0] for row in rows))

    def close(self) -> None:
        self.connection.close()
