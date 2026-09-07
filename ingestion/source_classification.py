"""Rule-based source classification (spec §7) — never inferred by an LLM, so a piece of
secondary commentary can never silently render as primary authority."""

from knowledge.models import SourceType

_PROVIDER_DEFAULT_SOURCE_TYPE: dict[str, SourceType] = {
    "courtlistener": SourceType.PRIMARY,
    "govinfo": SourceType.PRIMARY,
    "congress_gov": SourceType.QUASI_PRIMARY,
    "state_legislature": SourceType.PRIMARY,
    "law_review": SourceType.SECONDARY,
    "user_upload": SourceType.SECONDARY,
}


def classify_source_type(source_provider: str, doc_type: str) -> SourceType:
    if doc_type in ("case", "statute", "regulation") and source_provider in (
        "courtlistener",
        "govinfo",
        "state_legislature",
    ):
        return SourceType.PRIMARY
    return _PROVIDER_DEFAULT_SOURCE_TYPE.get(source_provider, SourceType.DISCOVERY)
