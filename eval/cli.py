"""Run live evaluation variants and write their results and a comparable-run report."""

import argparse
import json
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

import httpx

from assistant.api_client import connect
from assistant.llm import ModelClient, ModelUnavailable, sdk_sender
from assistant.pipeline import Steps
from assistant.settings import (
    COMPARISON_RUNTIME_MODEL,
    DEFAULT_RUNTIME_MODEL,
    GROQ_URL,
    MissingKey,
    Settings,
    load_settings,
)
from eval.compare import build as comparison
from eval.compare import reference_run
from eval.judge.calibrate import PAIRS, PROMPT_SHA256, Pair, calibrate, load_pairs
from eval.judge.calibrate import summary as calibration_summary
from eval.judge.judge import judge_cases
from eval.loader import Case, load_cases
from eval.local_api import ROOT, local_api
from eval.rate_limit import rate_limited_sender
from eval.report import build
from eval.results import RESULTS, score_all, summary, write_run
from eval.runner import run_cases, validate_cases
from eval.usage import MeteredModel, UsageCapture, model_usage

CASE_FILES = {
    "dev": "dev.jsonl",
    "baseline": "test.jsonl",
    "improved": "test.jsonl",
    "dev-groq20b": "dev.jsonl",
}
MATCH = {"dev": True, "baseline": False, "improved": True, "dev-groq20b": True}


class EvaluationInputError(ValueError):
    """A loader or labeling error whose message is safe to show."""


def validate_calibration(pairs: list[Pair]) -> None:
    if len(pairs) != 20 or len({pair.id for pair in pairs}) != 20:
        raise EvaluationInputError("Calibration needs exactly 20 uniquely identified pairs.")
    if any(pair.label is None for pair in pairs):
        raise EvaluationInputError("Label every calibration pair true or false before calibrating.")


def input_pairs(path: Path = PAIRS) -> list[Pair]:
    try:
        pairs = load_pairs(path)
    except (ValueError, OSError):
        raise EvaluationInputError("The calibration file is missing or invalid.") from None
    validate_calibration(pairs)
    return pairs


def saved_calibration(directory: Path) -> dict | None:
    path = directory / "calibration.json"
    if not path.is_file():
        return None
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise EvaluationInputError(
            "The saved judge calibration is invalid; review it first."
        ) from None
    if not isinstance(result, dict) or result.get("prompt_sha256") != PROMPT_SHA256:
        raise EvaluationInputError(
            "The judge prompt changed after calibration; restore the calibrated prompt and review."
        )
    return result


def require_calibration(directory: Path, judge_role: dict) -> dict:
    result = saved_calibration(directory)
    if result is None:
        raise EvaluationInputError("Calibrate the labeled judge pairs before test-set runs.")
    if (
        judge_role.get("provider") != "groq"
        or judge_role.get("base_url") != GROQ_URL
        or result.get("total") != 20
        or type(result.get("agreed")) is not int
        or not 0 <= result["agreed"] <= 20
        or result.get("rate") != result["agreed"] / 20
        or not isinstance(result.get("disagreements"), list)
        or len(result["disagreements"]) != 20 - result["agreed"]
        or result.get("judge") != judge_role
        or result.get("service_tier") != "provider_default"
    ):
        raise EvaluationInputError("The saved calibration does not match this Groq judge.")
    return result


def input_cases(path: Path) -> list[Case]:
    try:
        cases = load_cases(path)
        validate_cases(cases)
    except FileNotFoundError:
        raise EvaluationInputError(
            "Evaluation input file is missing; finish drafting and labeling the cases."
        ) from None
    except ValueError as error:
        # These two eval-owned validators report line/type or missing labels, never case text.
        raise EvaluationInputError(str(error)) from None
    return cases


def implementation_digest() -> str:
    """Fingerprint code, prompts and public data; keys and case files are never included."""
    digest = sha256()
    files = [
        path
        for package in ("assistant", "eval")
        for path in (ROOT / package).rglob("*")
        if path.suffix in {".py", ".txt"}
    ]
    for folder in ("catalog", "data", "policies"):
        files.extend((ROOT / folder).glob("*.json"))
        files.extend((ROOT / folder).glob("*.yaml"))
        files.extend((ROOT / folder).glob("*.md"))
    for path in sorted(files):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def metadata(cases: list[Case], settings: Settings) -> dict:
    case_text = json.dumps([case.model_dump(mode="json") for case in cases], sort_keys=True)
    return {
        "exact_match": settings.exact_match,
        "configuration": {
            "mode": settings.llm,
            "runtime": asdict(settings.runtime),
            "judge": asdict(settings.judge),
            "case_sha256": sha256(case_text.encode()).hexdigest(),
            "implementation_sha256": implementation_digest(),
            "judge_prompt_sha256": PROMPT_SHA256,
            "judge_service_tier": "provider_default",
        },
    }


def evaluate(
    name: str,
    cases: list[Case],
    settings: Settings,
    runtime: ModelClient,
    judge: ModelClient,
    http: httpx.Client,
    steps: Steps | None = None,
    directory: Path = RESULTS,
) -> dict:
    validate_cases(cases)
    records = run_cases(cases, settings, runtime, http, steps)
    judge_cases(judge, records)
    extra = {**metadata(cases, settings), "runtime_usage": model_usage(runtime)}
    return write_run(name, records, score_all(records), extra, directory=directory)


def refresh_report(directory: Path = RESULTS) -> bool:
    paths = [directory / f"{name}.json" for name in ("baseline", "improved")]
    if not all(path.is_file() for path in paths):
        return False
    baseline, improved = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    same = baseline.get("configuration") == improved.get("configuration")
    flags = baseline.get("exact_match") is False and improved.get("exact_match") is True
    if not baseline.get("configuration") or not same or not flags:
        raise ValueError(
            "saved baseline and improved runs have incompatible cases or configuration"
        )
    calibration = require_calibration(directory, improved["configuration"]["judge"])
    report = build(baseline, improved, calibration, PROMPT_SHA256)
    (directory.parent / "REPORT.md").write_text(report, encoding="utf-8", newline="\n")
    return True


@contextmanager
def live_models(
    settings: Settings, *, judge_only: bool = False
) -> Iterator[tuple[ModelClient, ...]]:
    with ExitStack() as resources:
        models = []
        roles = (settings.judge,) if judge_only else (settings.runtime, settings.judge)
        for role in roles:
            if role.provider != "groq" or role.base_url != GROQ_URL:
                raise EvaluationInputError("Evaluation model requests must use the Groq API.")
            usage = UsageCapture()
            http = resources.enter_context(
                httpx.Client(
                    timeout=role.timeout,
                    event_hooks={"request": [usage.request], "response": [usage.response]},
                )
            )
            send = rate_limited_sender(sdk_sender(role, settings.api_key(role), http), role)
            models.append(MeteredModel(role, send, usage))
        yield tuple(models)


def run_calibration(
    pairs: list[Pair], settings: Settings, *, models=live_models, directory: Path = RESULTS
) -> dict:
    validate_calibration(pairs)
    saved_calibration(directory)  # A saved prompt stays frozen before any new request.
    if (
        settings.llm != "live"
        or settings.judge.provider != "groq"
        or settings.judge.base_url != GROQ_URL
    ):
        raise EvaluationInputError("Judge calibration requires live mode and the Groq judge.")
    settings.api_key(settings.judge)
    with models(settings, judge_only=True) as (judge,):
        result = calibrate(judge, pairs)
    result.update(
        judge=asdict(settings.judge),
        service_tier="provider_default",
        label_source="AI (user authorized)",
    )
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "calibration.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    markdown = (
        f"# Judge calibration\n\n{calibration_summary(result)}\n\n"
        f"Prompt SHA256: `{PROMPT_SHA256}`\n\nProcessing: Groq provider default.\n\n"
        "Label source: AI (user authorized), without independent human review.\n"
    )
    (directory / "calibration.md").write_text(markdown, encoding="utf-8", newline="\n")
    refresh_report(directory)
    return result


def run_live(
    name: str,
    cases: list[Case],
    settings: Settings,
    *,
    models=live_models,
    serve=local_api,
    directory: Path = RESULTS,
    steps: Steps | None = None,
) -> dict:
    validate_cases(cases)
    expected_model = COMPARISON_RUNTIME_MODEL if name == "dev-groq20b" else DEFAULT_RUNTIME_MODEL
    if (
        settings.llm != "live"
        or settings.runtime.model != expected_model
        or settings.runtime.model == settings.judge.model
        or any(
            role.provider != "groq" or role.base_url != GROQ_URL
            for role in (settings.runtime, settings.judge)
        )
    ):
        raise ValueError("evaluation requires its selected Groq runtime and a different Groq judge")
    if settings.exact_match is not MATCH[name]:
        raise ValueError("the exact-match setting does not match this evaluation variant")
    reference = None
    if name == "dev-groq20b":
        reference = reference_run(directory, metadata(cases, settings))
    elif name != "dev":
        require_calibration(directory, asdict(settings.judge))
    for role in (settings.runtime, settings.judge):
        settings.api_key(role)
    with (
        models(settings) as (runtime, judge),
        serve(settings) as isolated,
        connect(isolated) as http,
    ):
        result = evaluate(name, cases, isolated, runtime, judge, http, steps, directory)
    if reference is not None:
        (directory / "dev-groq20b.md").write_text(
            comparison(reference, result), encoding="utf-8", newline="\n"
        )
    elif name != "dev":
        refresh_report(directory)
    return result


def main(argv: list[str] | None = None, settings: Settings | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", choices=(*CASE_FILES, "calibrate"))
    args = parser.parse_args(argv)
    if args.run == "calibrate":
        result = run_calibration(input_pairs(), settings or load_settings())
        print(calibration_summary(result))
        return
    cases = input_cases(ROOT / "eval" / "cases" / CASE_FILES[args.run])
    result = run_live(args.run, cases, settings or load_settings())
    print(summary(args.run, result["metrics"]))


def entrypoint() -> None:
    try:
        main()
    except MissingKey as error:
        raise SystemExit(str(error)) from None
    except EvaluationInputError as error:
        raise SystemExit(str(error)) from None
    except FileNotFoundError:
        raise SystemExit(
            "Evaluation input file is missing; finish drafting and labeling the cases."
        ) from None
    except (ValueError, RuntimeError, OSError, httpx.HTTPError, ModelUnavailable) as error:
        print(
            f"Evaluation stopped ({type(error).__name__}); check case labels and run settings.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    entrypoint()
