"""Citation precision/recall against the gold-standard set (docs/architecture.md §9).

Usage: python -m evaluation.run_eval
"""

import json
from dataclasses import dataclass
from pathlib import Path

from agents.orchestrator import run_research
from research.schemas import ResearchMode, StructuredAnswer

GOLD_DIR = Path(__file__).parent / "gold_dataset"


@dataclass
class EvalResult:
    question: str
    precision: float
    recall: float


def _cited_strings(answer: StructuredAnswer) -> set[str]:
    strings = set()
    for claim in [*answer.binding_authorities, *answer.persuasive_authorities]:
        if claim.source and claim.source.citation_string:
            strings.add(claim.source.citation_string)
    return strings


def evaluate_case(case: dict) -> EvalResult:
    final_state = run_research(
        case["question"], case["jurisdiction"], [ResearchMode.DIRECT, ResearchMode.STATUTORY]
    )
    answer = StructuredAnswer.model_validate(final_state["final_answer"])

    expected = set(case.get("expected_binding_authorities", []))
    actual = _cited_strings(answer)

    true_positives = len(expected & actual)
    precision = true_positives / len(actual) if actual else 0.0
    recall = true_positives / len(expected) if expected else 1.0
    return EvalResult(question=case["question"], precision=precision, recall=recall)


def main() -> None:
    cases = [json.loads(p.read_text()) for p in GOLD_DIR.glob("*.json")]
    if not cases:
        print(f"No gold cases found in {GOLD_DIR} — see schema.md to add some.")
        return

    results = [evaluate_case(case) for case in cases]
    avg_precision = sum(r.precision for r in results) / len(results)
    avg_recall = sum(r.recall for r in results) / len(results)
    print(f"{len(results)} cases — avg precision {avg_precision:.2f}, avg recall {avg_recall:.2f}")
    for r in results:
        print(f"  {r.question[:60]!r}: precision={r.precision:.2f} recall={r.recall:.2f}")


if __name__ == "__main__":
    main()
