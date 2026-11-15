"""Validate a matching Groq development run and compare runtime accuracy, latency and cost."""

import json
import math
from dataclasses import asdict
from pathlib import Path

from assistant.settings import runtime_role
from eval.results import failed_cases, ms, percent
from eval.usage import PRICES, PRICING_DATE


def reference_run(directory: Path, metadata: dict) -> dict:
    """Reject missing or stale reference results before any model or API starts."""
    try:
        raw = json.loads((directory / "dev.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError(
            "Run eval-dev first: its saved Groq results are missing or invalid."
        ) from None
    configuration = {**metadata["configuration"], "runtime": asdict(runtime_role())}
    if (
        not isinstance(raw, dict)
        or raw.get("run") != "dev"
        or raw.get("exact_match") is not True
        or raw.get("configuration") != configuration
        or "runtime_usage" not in raw
    ):
        raise ValueError("Run eval-dev again: its cases, configuration or usage capture is stale.")
    try:
        comparison_rows(raw)
    except (KeyError, TypeError, ValueError):
        raise ValueError("Run eval-dev again: its saved metrics are invalid.") from None
    return raw


def comparison_rows(run: dict) -> dict[str, str]:
    accuracy, latency = (run["metrics"][name] for name in ("accuracy", "latency"))
    usage = run["runtime_usage"]
    if not isinstance(usage, dict):
        raise ValueError("invalid runtime usage")
    cost = usage.get("estimated_cost_usd")
    if cost is not None and (type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0):
        raise ValueError("invalid estimated runtime cost")
    shown = "unavailable" if cost is None else f"${cost:.8f}"
    if cost is not None and usage.get("unaccounted", 0):
        shown = f"at least {shown} ({usage['unaccounted']} attempts without usage)"
    return {
        "Answer accuracy": percent(accuracy["passed"], accuracy["total"]),
        "Latency p50 / p95": f"{ms(latency['p50_ms'])} / {ms(latency['p95_ms'])}",
        "Estimated runtime cost (USD)": shown,
    }


def build(baseline: dict, comparison: dict) -> str:
    before, after = comparison_rows(baseline), comparison_rows(comparison)
    failures = failed_cases(comparison["metrics"])
    lines = [
        "# Development runtime comparison",
        "",
        "The development cases, exact matching, prompts, policy and Qwen judge are the same;"
        " settings select the Groq runtime model.",
        "Case expectations are AI labels assigned on the user's instruction; independent human"
        " validation remains pending.",
        "",
        "| Metric | Groq GPT-OSS 120B | Groq GPT-OSS 20B |",
        "| --- | --- | --- |",
        *[f"| {name} | {before[name]} | {after[name]} |" for name in before],
        "",
        "Cost is estimated from actual provider prompt, cached-input, cache-write and completion"
        " token counts. Completion totals already include reasoning tokens. Rate-limited (429)"
        " attempts return no completion and count as unbilled. Any other attempt without usage,"
        " such as a timeout, is counted but not priced, so that cost reads 'at least'. Unknown"
        " pricing and unsupported cache writes make cost unavailable. Judge calls are excluded"
        " from both runtime cost and stage latency.",
        "",
        f"Pricing verified {PRICING_DATE}, USD per million tokens:",
        "",
    ]
    for (provider, model), price in PRICES.items():
        write = "unsupported" if price["cache_write"] is None else f"${price['cache_write']}"
        lines.append(
            f"- [{provider} {model}]({price['source']}): input ${price['input']},"
            f" cached input ${price['cached_input']}, cache write {write},"
            f" output ${price['output']}."
        )
    lines += ["", "## Failed GPT-OSS 20B cases", ""]
    lines += [f"- {case}: {'; '.join(reasons)}" for case, reasons in failures.items()] or ["None."]
    return "\n".join(lines) + "\n"
