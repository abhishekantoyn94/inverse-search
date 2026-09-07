"""The only place agents call OpenAI for structured reasoning.

`structured_complete` forces the model to answer inside a caller-given Pydantic schema
so agent output is always typed data, never free prose an agent could slip an invented
citation into. Grounding is enforced by what the caller puts in `context` (only
AuthorityResult objects from retrieval.toolkit) — never the model's parametric memory.
"""

from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from settings import settings

T = TypeVar("T", bound=BaseModel)

_client = OpenAI(api_key=settings.openai_api_key)

STRICT_GROUNDING = (
    "You are a legal research agent. You may only refer to cases, statutes, or "
    "quotations that appear verbatim in the RETRIEVED AUTHORITIES provided below. "
    "Never name a case, section, or quotation from memory. If the retrieved "
    "authorities are insufficient to support a claim, classify it as 'inference', "
    "'analogy', 'speculation', or 'unresolved' rather than 'authority', and say so "
    "explicitly. Every claim of type 'authority' must include the exact "
    "document_id/section_id of the authority it relies on."
)

# For calls that are allowed to reason from general legal knowledge (the preliminary
# answer, and synthesis's prose) — the one rule that actually prevents fabricated
# authority still applies: never invent a SPECIFIC case name, statute citation, docket
# number, or quotation. General legal doctrine can be discussed by name (e.g.
# "qualified immunity," "strict scrutiny") without a pinpoint cite; a specific
# authority may only be named if it already appears in the provided context below.
OPEN_REASONING = (
    "You are a knowledgeable legal analyst. Give a complete, substantive answer "
    "drawing on general legal knowledge, doctrine, and the context provided below "
    "(retrieved authorities, web search results). You may discuss legal doctrines "
    "and principles by name generally (e.g. 'qualified immunity', 'strict scrutiny') "
    "without a pinpoint citation. You must NOT invent a specific case name, statute "
    "citation, docket number, or quotation that isn't already given to you in the "
    "context below — if you want to reference a specific authority, it must be one "
    "provided to you, not one you recall or infer might exist."
)


def structured_complete(
    system_prompt: str,
    user_content: str,
    response_model: type[T],
    model: str | None = None,
    grounding: str = STRICT_GROUNDING,
) -> T:
    completion = _client.beta.chat.completions.parse(
        model=model or settings.openai_chat_model,
        messages=[
            {"role": "system", "content": f"{grounding}\n\n{system_prompt}"},
            {"role": "user", "content": user_content},
        ],
        response_format=response_model,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("Model refused to produce structured output")
    return parsed
