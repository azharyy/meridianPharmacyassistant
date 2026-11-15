"""Load the independently authored brand and everyday-word search aliases."""

from pathlib import Path

import yaml

from assistant.retrieval.exact import normalize


def load_aliases(path: Path) -> dict[str, str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(
        isinstance(alias, str)
        and isinstance(target, str)
        and normalize(alias)
        and normalize(target)
        for alias, target in data.items()
    ):
        raise ValueError("Aliases must map nonempty phrases to nonempty catalog terms")
    if len({normalize(alias) for alias in data}) != len(data):
        raise ValueError("Alias phrases must be unique ignoring case and punctuation")
    return data
