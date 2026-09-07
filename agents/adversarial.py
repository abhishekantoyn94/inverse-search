from agents.llm import structured_complete
from agents.schemas import AdversarialOutput
from agents.state import ResearchState
from research.schemas import AdversarialAnalysis, ResearchMode

SYSTEM_PROMPT = (
    "You are acting as opposing counsel. Using ONLY the claims already gathered below "
    "(authorities supporting, authorities against, distinguishing authorities, inverse "
    "research), construct: the strongest argument FOR the user's proposition, the "
    "strongest argument AGAINST it, the weaknesses in the user's position, and possible "
    "responses to the strongest opposing argument. Do not introduce any new case or "
    "statute that isn't already one of these claims — reuse their exact source refs. "
    "Every claim you output must carry claim_type 'authority' only if it reuses an "
    "existing claim's source; otherwise use 'inference' or 'analogy' with no source."
)


def _render_claims(label: str, claims: list) -> str:
    if not claims:
        return f"{label}: (none)"
    lines = [f"{label}:"]
    for c in claims:
        source = f"[document_id={c.source.document_id} section_id={c.source.section_id}]" if c.source else "[no source]"
        lines.append(f"- {source} {c.text}")
    return "\n".join(lines)


def run(state: ResearchState) -> ResearchState:
    modes = state.get("requested_modes", [])
    if ResearchMode.ADVERSARIAL not in modes and ResearchMode.PRECEDENT_ATTACK not in modes:
        return state

    inverse = state.get("inverse_research")
    context = "\n\n".join(
        [
            f"PROPOSITION:\n{state['question']}",
            _render_claims("Authorities supporting", state.get("authorities_supporting", [])),
            _render_claims("Authorities against", state.get("authorities_against", [])),
            _render_claims("Distinguishing authorities", state.get("distinguishing_authorities", [])),
            _render_claims(
                "Authorities supporting the inverse proposition",
                inverse.authorities_supporting_inverse if inverse else [],
            ),
        ]
    )
    result: AdversarialOutput = structured_complete(SYSTEM_PROMPT, context, AdversarialOutput, model=state.get("model"))
    return {
        **state,
        "adversarial_analysis": AdversarialAnalysis(
            strongest_argument_for=result.strongest_argument_for,
            strongest_argument_against=result.strongest_argument_against,
            weaknesses=result.weaknesses,
            likely_opposing_authorities=state.get("authorities_against", [])
            + state.get("distinguishing_authorities", []),
            possible_responses=result.possible_responses,
        ),
    }
