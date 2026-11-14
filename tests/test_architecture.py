"""Module boundaries, checked on every `make check`.

The rules are explained in docs/PLAN.md under "Module map and rules".
If a rule blocks a change, raise it with the user. Never edit this file to get past it.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Each top-level package, and the other project packages it may import.
PACKAGE_MAY_IMPORT: dict[str, set[str]] = {
    "contracts": set(),
    "api": {"contracts"},
    "assistant": {"contracts"},
    "eval": {"contracts", "assistant"},
    "scripts": {"contracts"},
}

# Inside assistant/: the modules any step may use, and the two that wire the steps together.
SHARED = {"settings", "llm", "api_client", "session", "policy", "templates"}
COMPOSERS = {"pipeline", "app"}

# Packages in which every module needs a test file at the mirrored path.
NEEDS_TESTS = ("assistant", "api")


def python_files(package: str) -> Iterator[Path]:
    """Every Python file in a top-level package; nothing if the package doesn't exist yet."""
    yield from sorted((ROOT / package).rglob("*.py"))


def module_parts(path: Path) -> list[str]:
    """`assistant/safety/reviewer.py` becomes `["assistant", "safety", "reviewer"]`."""
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    return parts[:-1] if parts[-1] == "__init__" else parts


def imported_names(path: Path) -> Iterator[str]:
    """Absolute dotted names of everything a file imports, with relative imports resolved."""
    package = list(path.relative_to(ROOT).parent.parts)
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            base = package[: len(package) - node.level + 1] if node.level else []
            base += node.module.split(".") if node.module else []
            for alias in node.names:
                yield ".".join([*base, alias.name])


def unit_of(parts: list[str]) -> str:
    """The module or folder directly under assistant/ that a file belongs to."""
    return parts[1] if len(parts) > 1 else ""


def test_packages_import_only_what_they_may() -> None:
    problems = []
    for package, allowed in PACKAGE_MAY_IMPORT.items():
        for path in python_files(package):
            for name in imported_names(path):
                top = name.split(".")[0]
                if top in {*PACKAGE_MAY_IMPORT, "tests"} and top != package and top not in allowed:
                    where = path.relative_to(ROOT)
                    problems.append(f"{where} imports {name}: {package}/ may not import {top}/")
    assert not problems, "\n" + "\n".join(problems)


def test_assistant_steps_do_not_import_each_other() -> None:
    """Only pipeline.py and app.py wire steps together; a step gets what it needs passed in."""
    problems = []
    for path in python_files("assistant"):
        unit = unit_of(module_parts(path))
        if not unit or unit in COMPOSERS:
            continue
        allowed = {unit, "settings"} if unit in SHARED else {unit, *SHARED}
        for name in imported_names(path):
            parts = name.split(".")
            if parts[0] == "assistant" and len(parts) > 1 and parts[1] not in allowed:
                problems.append(
                    f"{path.relative_to(ROOT)} imports {name}: {unit} may import only "
                    f"{sorted(allowed)} from assistant/. Pass the dependency in from pipeline.py."
                )
    assert not problems, "\n" + "\n".join(problems)


def test_every_module_has_a_test_file() -> None:
    problems = []
    for package in NEEDS_TESTS:
        for path in python_files(package):
            if path.name == "__init__.py":
                continue
            relative = path.relative_to(ROOT)
            expected = ROOT / "tests" / relative.parent / f"test_{path.name}"
            if not expected.exists():
                problems.append(f"{relative} has no test file at {expected.relative_to(ROOT)}")
    assert not problems, "\n" + "\n".join(problems)
