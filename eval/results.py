"""Score one run with every metric and write its raw JSON and a short Markdown summary."""

import json
from pathlib import Path

from eval.metrics import accuracy, emergency, escalation, groundedness, latency, privacy, retrieval
from eval.runner import RecordedCase

RESULTS = Path(__file__).parent / "results"
METRICS = {
    "accuracy": accuracy.score,
    "retrieval": retrieval.score,
    "groundedness": groundedness.score,
    "escalation": escalation.score,
    "emergency": emergency.score,
    "privacy": privacy.score,
    "latency": latency.score,
}


def percent(count: int, total: int) -> str:
    return f"{count}/{total} ({count / total:.1%})" if total else f"{count}/{total} (n/a)"


def ms(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0f} ms"


def score_all(cases: list[RecordedCase]) -> dict:
    return {name: score(cases) for name, score in METRICS.items()}


def failed_cases(metrics: dict, names: tuple[str, ...] = tuple(METRICS)) -> dict[str, list[str]]:
    """Every failed case with each named metric's reasons, by case id."""
    failures: dict[str, list[str]] = {}
    for name in names:
        for case, reasons in metrics[name].get("failed_cases", {}).items():
            failures.setdefault(case, []).extend(f"{name}: {reason}" for reason in reasons)
    return dict(sorted(failures.items()))


def metric_lines(metrics: dict) -> list[str]:
    a, r, g, e = (metrics[name] for name in ("accuracy", "retrieval", "groundedness", "escalation"))
    m, p, t = metrics["emergency"], metrics["privacy"], metrics["latency"]
    return [
        f"- Answer accuracy: {percent(a['passed'], a['total'])}",
        f"- Retrieval success: {percent(r['passed'], r['total'])}",
        f"- Groundedness: {percent(g['grounded'], g['factual'])} factual replies;"
        f" {g['fact_free']} fact-free replies counted apart",
        f"- Escalation precision: {percent(e['tp'], e['tp'] + e['fp'])};"
        f" recall: {percent(e['tp'], e['tp'] + e['fn'])}",
        f"- Emergency recall: {percent(m['passed'], m['total'])}",
        f"- Cross-customer leaks: {percent(p['leaks'], p['total'])}",
        f"- Latency per turn: p50 {ms(t['p50_ms'])}, p95 {ms(t['p95_ms'])}"
        f" over {t['count']} turns, judge time excluded",
    ]


def summary(name: str, metrics: dict) -> str:
    failures = failed_cases(metrics)
    lines = [f"# Results: {name}", "", *metric_lines(metrics), "", "## Failed cases", ""]
    lines += [f"- {case}: {'; '.join(reasons)}" for case, reasons in failures.items()] or ["None."]
    return "\n".join(lines) + "\n"


def write_run(
    name: str,
    cases: list[RecordedCase],
    metrics: dict,
    extra: dict | None = None,
    markdown: str | None = None,
    directory: Path = RESULTS,
) -> dict:
    """Write <name>.json (every recorded turn) and <name>.md; return the raw results."""
    raw = {"run": name, **(extra or {}), "metrics": metrics}
    raw["cases"] = [case.model_dump(mode="json") for case in cases]
    directory.mkdir(parents=True, exist_ok=True)
    text = json.dumps(raw, indent=2, ensure_ascii=False) + "\n"
    (directory / f"{name}.json").write_text(text, encoding="utf-8", newline="\n")
    summary_text = markdown or summary(name, metrics)
    (directory / f"{name}.md").write_text(summary_text, encoding="utf-8", newline="\n")
    return raw
