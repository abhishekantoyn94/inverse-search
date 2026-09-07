from agents.llm import OPEN_REASONING, structured_complete
from agents.schemas import SynthesisTextOutput
from agents.state import ResearchState
from research.schemas import AdversarialAnalysis, InverseResearch, ResearchMode, StructuredAnswer
from retrieval.websearch import format_web_results_for_prompt

SYSTEM_PROMPT = (
    "Write the short_answer (a genuinely substantive, complete answer — several "
    "sentences, not a hedge) and conclusion for this legal research answer. Use the "
    "PRELIMINARY ANALYSIS and WEB SEARCH RESULTS below as your primary reasoning "
    "material — this is what makes the answer actually useful even when few "
    "authorities were retrieved from the local corpus. Weave in the VERIFIED CLAIMS "
    "where they support or refine the analysis, and say so when they do. Do not "
    "invent a specific case name, statute citation, or quotation beyond what's given "
    "in the verified claims below — general doctrine can be discussed by name. Then "
    "list unresolved_questions and research_gaps: genuine open questions, not a "
    "disclaimer that no authorities exist when the preliminary analysis already "
    "covers the doctrine."
)

_IMPLEMENTED_MODES = {
    ResearchMode.DIRECT, ResearchMode.STATUTORY, ResearchMode.FACT_SIMILARITY,
    ResearchMode.LEGAL_SIMILARITY, ResearchMode.CITATION, ResearchMode.INVERSE,
    ResearchMode.ADVERSARIAL, ResearchMode.PRECEDENT_ATTACK,
}


def run(state: ResearchState) -> ResearchState:
    requested = state.get("requested_modes", [])
    not_yet_researched = [m for m in requested if m not in _IMPLEMENTED_MODES]

    context_lines = [
        f"PROPOSITION: {state['question']}",
        f"ISSUES: {'; '.join(state.get('issues', []))}",
        "",
        "PRELIMINARY ANALYSIS (general legal reasoning, not yet checked against retrieved authorities):",
        state.get("preliminary_analysis", "(none)"),
        "",
        "WEB SEARCH RESULTS:",
        format_web_results_for_prompt(state.get("web_results", [])),
        "",
        "VERIFIED CLAIMS (from the local legal corpus):",
    ]
    for label, key in [
        ("Governing statutes", "governing_statutes"),
        ("Binding authorities", "binding_authorities"),
        ("Persuasive authorities", "persuasive_authorities"),
        ("Authorities supporting", "authorities_supporting"),
        ("Authorities against", "authorities_against"),
        ("Distinguishing authorities", "distinguishing_authorities"),
    ]:
        claims = state.get(key, [])
        context_lines.append(f"{label}: {len(claims)} claim(s)")
        context_lines.extend(f"  - {c.text}" for c in claims)

    text: SynthesisTextOutput = structured_complete(
        SYSTEM_PROMPT,
        "\n".join(context_lines),
        SynthesisTextOutput,
        model=state.get("model"),
        grounding=OPEN_REASONING,
    )

    jurisdiction = state.get("target_jurisdiction", "unspecified")
    jurisdiction_note = (
        f"Research was limited to {jurisdiction} sources available in Inverse's corpus "
        f"(CourtListener/GovInfo coverage); it is not exhaustive of every court or reporter."
    )
    date_note = (
        "Authority currency (whether later courts have overruled/criticised an authority) "
        "reflects an open citation-graph approximation, not a Shepard's/KeyCite-equivalent "
        "guarantee — verify currency independently before relying on any single authority."
    )

    answer = StructuredAnswer(
        question=state["question"],
        short_answer=text.short_answer,
        jurisdiction=jurisdiction,
        material_facts=state.get("material_facts", []),
        issues=state.get("issues", []),
        governing_statutes=state.get("governing_statutes", []),
        binding_authorities=state.get("binding_authorities", []),
        persuasive_authorities=state.get("persuasive_authorities", []),
        factually_similar_authorities=state.get("factually_similar_authorities", []),
        legally_similar_authorities=state.get("legally_similar_authorities", []),
        authorities_supporting=state.get("authorities_supporting", []),
        authorities_against=state.get("authorities_against", []),
        distinguishing_authorities=state.get("distinguishing_authorities", []),
        adversarial_analysis=state.get(
            "adversarial_analysis",
            AdversarialAnalysis(
                strongest_argument_for={"text": "Not researched in this session.", "claim_type": "unresolved"},
                strongest_argument_against={"text": "Not researched in this session.", "claim_type": "unresolved"},
            ),
        ),
        inverse_research=state.get(
            "inverse_research", InverseResearch(inverse_proposition="Not researched in this session.")
        ),
        comparative_authorities=[],
        novel_or_analogous_authorities=[],
        unresolved_questions=text.unresolved_questions,
        research_gaps=text.research_gaps,
        conclusion=text.conclusion,
        jurisdiction_coverage_note=jurisdiction_note,
        date_coverage_note=date_note,
        modes_not_yet_researched=not_yet_researched,
        web_verification=state.get("web_results", []),
    )
    return {**state, "final_answer": answer.model_dump(mode="json")}
