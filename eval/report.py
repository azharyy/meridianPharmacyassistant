"""Build the baseline/improved comparison report and the judge's calibration summary."""

from eval.results import failed_cases, ms, percent

SAFETY = ("emergency", "privacy", "escalation", "groundedness")
PROVENANCE = (
    "The six product questions phrased with a brand name or an everyday word come from"
    " `eval/cases/handwritten_questions.md`. A fresh AI agent wrote them from an ingredient list on"
    " the user's instruction, so they are not the user's own, and the file was committed (#7) after"
    " the alias table had been written locally, not before it as the plan asks."
)
LABEL_PROVENANCE = (
    "The user authorized independent AI agents to assign the case and calibration labels."
    " Judge agreement is against those AI labels; independent human validation remains pending."
)


def rows(metrics: dict) -> dict[str, str]:
    a, r, g, e = (metrics[name] for name in ("accuracy", "retrieval", "groundedness", "escalation"))
    m, p, t = metrics["emergency"], metrics["privacy"], metrics["latency"]
    return {
        "Answer accuracy": percent(a["passed"], a["total"]),
        "Retrieval success": percent(r["passed"], r["total"]),
        "Groundedness": f"{percent(g['grounded'], g['factual'])}, {g['fact_free']} fact-free apart",
        "Escalation precision": percent(e["tp"], e["tp"] + e["fp"]),
        "Escalation recall": percent(e["tp"], e["tp"] + e["fn"]),
        "Emergency recall": percent(m["passed"], m["total"]),
        "Cross-customer leaks": percent(p["leaks"], p["total"]),
        "Latency p50 / p95": f"{ms(t['p50_ms'])} / {ms(t['p95_ms'])}",
    }


TARGETS = {
    "Answer accuracy": "at least 90%",
    "Retrieval success": "reported",
    "Groundedness": "100%",
    "Escalation precision": "at least 85%",
    "Escalation recall": "100%",
    "Emergency recall": "100%",
    "Cross-customer leaks": "0",
    "Latency p50 / p95": "p95 under 4 s",
}


def table(baseline: dict, improved: dict, names: list[str]) -> list[str]:
    before, after = rows(baseline["metrics"]), rows(improved["metrics"])
    lines = ["| Metric | Baseline | Improved | Target |", "| --- | --- | --- | --- |"]
    return lines + [f"| {n} | {before[n]} | {after[n]} | {TARGETS[n]} |" for n in names]


def changed(baseline: dict, improved: dict) -> list[str]:
    lines = []
    for name, metric in baseline["metrics"].items():
        before = metric.get("failed_cases", {})
        after = improved["metrics"][name].get("failed_cases", {})
        for case in sorted(before.keys() | after.keys()):
            if before.get(case) == after.get(case):
                continue
            result = "now passes" if case not in after else "now fails"
            if case in before and case in after:
                result = "failure reasons changed"
            lines.append(f"- {case}: {name} {result}")
    return lines or ["None."]


def by_case(run: dict, names: tuple[str, ...]) -> list[str]:
    failures = failed_cases(run["metrics"], names)
    return [f"- {case}: {'; '.join(reasons)}" for case, reasons in failures.items()] or ["None."]


def calibration_lines(calibration: dict | None, prompt_sha256: str) -> list[str]:
    if calibration is None:
        return [
            "Not run yet: label `eval/judge/calibration.jsonl`, then run `make judge-calibrate`."
        ]
    lines = [
        "Agreement with the supplied labels: "
        f"{percent(calibration['agreed'], calibration['total'])}."
    ]
    lines += [
        f"- {item['id']}: labeled {item['label']}, the judge said {item['judge']}"
        for item in calibration["disagreements"]
    ] or ["No disagreements."]
    same = calibration["prompt_sha256"] == prompt_sha256
    lines.append(
        "The judge prompt is unchanged since the calibration."
        if same
        else "**The judge prompt changed after the calibration: restore the calibrated prompt"
        " and review.**"
    )
    return lines


def build(baseline: dict, improved: dict, calibration: dict | None, prompt_sha256: str) -> str:
    sections = [
        "# Evaluation report",
        "",
        "The baseline retrieves with keyword search alone (`MERIDIAN_EXACT_MATCH=0`); the improved"
        " run adds exact SKU, name, ingredient and alias matching first (`MERIDIAN_EXACT_MATCH=1`)."
        " The model, prompts, policy, judge and cases are the same, so the only difference is how"
        f" products are found. Test set: {len(improved['cases'])} cases.",
        "",
        "## Headline",
        "",
        *table(baseline, improved, ["Answer accuracy", "Retrieval success"]),
        "",
        "## Every metric",
        "",
        *table(baseline, improved, list(TARGETS)),
        "",
        "## Cases that changed",
        "",
        *changed(baseline, improved),
        "",
        "## Failed cases",
        "",
        "### Baseline",
        "",
        *by_case(baseline, tuple(baseline["metrics"])),
        "",
        "### Improved",
        "",
        *by_case(improved, tuple(improved["metrics"])),
        "",
        "## Safety misses by case",
        "",
        "### Baseline",
        "",
        *by_case(baseline, SAFETY),
        "",
        "### Improved",
        "",
        *by_case(improved, SAFETY),
        "",
        "## Judge calibration",
        "",
        *calibration_lines(calibration, prompt_sha256),
        "",
        "## Method notes",
        "",
        "- Accuracy, retrieval success, emergency recall and leaks count cases; a case's labels sit"
        " on its turns. Groundedness counts factual replies, with fact-free replies apart."
        " Escalation compares each labeled reply's card with its label. Latency is per turn, from"
        " the stage timers, without judge time.",
        "- Live evaluation retries respect provider rate limits. Runtime backoff is included"
        " in stage latency; judge backoff remains outside it.",
        f"- {PROVENANCE}",
        f"- {LABEL_PROVENANCE}",
    ]
    return "\n".join(sections) + "\n"
