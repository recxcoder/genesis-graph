from app.graph.reader import (
    get_known_facts,
    get_prior_queries,
    multihop_related_facts
)


def build_context(session_id: str, current_query: str) -> str:
    
    prior_queries  = get_prior_queries(session_id)
    known_facts    = get_known_facts(session_id, limit=8)
    related_facts  = multihop_related_facts(session_id, current_query)

    if not prior_queries and not known_facts:
        return "No prior knowledge found. Start fresh research."

    parts = []

    if prior_queries:
        lines = "\n".join(f"- {q}" for q in prior_queries)
        parts.append(f"## What you have already searched for:\n{lines}")

    if known_facts:
        lines = "\n".join(f"- {f}" for f in known_facts)
        parts.append(f"## Verified facts you already know:\n{lines}")

    if related_facts:
        lines = "\n".join(f"- {f}" for f in related_facts)
        parts.append(f"## Related facts from prior research on '{current_query}':\n{lines}")

    return "\n\n".join(parts)