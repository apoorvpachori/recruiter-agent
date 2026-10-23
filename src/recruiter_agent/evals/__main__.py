"""Run the local synthetic agent evaluation suite."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from recruiter_agent.evals.runner import judge_result, load_cases, run_case, write_report
from recruiter_agent.settings import Settings

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "evals" / "cases" / "core.jsonl"
REPORT = ROOT / ".eval-results" / "latest.md"


def main() -> int:
    try:
        cases = load_cases(CASES)
    except Exception as exc:
        print(f"Could not load eval cases ({type(exc).__name__}).", file=sys.stderr)
        return 2

    with patch.dict(
        os.environ,
        {"LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"},
    ):
        settings = Settings()
        judge_model = None
        if settings.eval_judge_enabled:
            try:
                from recruiter_agent.providers.fireworks import create_fireworks_model

                judge_model = create_fireworks_model(settings)
            except Exception as exc:
                print(f"Could not configure LLM judge ({type(exc).__name__}).", file=sys.stderr)
                return 2
        results = [run_case(case, settings) for case in cases]
        if judge_model is not None:
            for case, result in zip(cases, results, strict=True):
                judge_result(case, result, judge_model)

    passed = sum(result.passed for result in results)
    write_report(REPORT, cases, results, judge_enabled=settings.eval_judge_enabled)
    judge_status = "enabled" if settings.eval_judge_enabled else "disabled"
    print(f"Agent evals: {passed}/{len(results)} passed (LLM judge {judge_status})")
    for result in results:
        print(f"{'PASS' if result.passed else 'FAIL'} {result.case_id}")
        for check in result.hard_checks:
            print(f"  {'PASS' if check.passed else 'FAIL'} {check.name}: {check.detail}")
        for trace in result.tool_trace:
            print(f"  TOOL {trace.name}")
            print(f"    args: {json.dumps(trace.args, ensure_ascii=False, default=str)}")
            print(f"    result: {json.dumps(trace.result, ensure_ascii=False, default=str)}")
        print(f"  Response: {result.response or '(empty)'}")
        if result.judge:
            print(
                "  Judge: "
                f"relevance={result.judge.answer_relevance}/2, "
                f"grounding={result.judge.evidence_grounding}/2, "
                f"uncertainty={result.judge.uncertainty_calibration}/2"
            )
            print(f"  Judge rationale: {result.judge.rationale}")
    print(f"Report: {REPORT.relative_to(ROOT)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
