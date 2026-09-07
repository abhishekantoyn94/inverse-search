from retrieval.toolkit import AuthorityResult


def format_authorities(authorities: list[AuthorityResult]) -> str:
    """Renders retrieved authorities as an enumerated block agents can point claims at
    by (document_id, section_id) — the only identifiers Source Verification trusts."""
    if not authorities:
        return "(no authorities retrieved)"
    blocks = []
    for a in authorities:
        blocks.append(
            f"[document_id={a.document_id} section_id={a.section_id}]\n"
            f"Title: {a.title}\n"
            f"Citation: {a.citation_string or 'n/a'}\n"
            f"Court: {a.court_name or 'n/a'} | Jurisdiction: {a.jurisdiction_name or 'n/a'}\n"
            f"Date: {a.date_decided_or_enacted or 'n/a'} | Source type: {a.source_type} | "
            f"Binding: {a.is_binding} | Authority score: {a.authority_score}\n"
            f"Locator: {a.locator or 'n/a'}\n"
            f"Extract: {a.extract}\n"
        )
    return "\n---\n".join(blocks)
