from corpussieve.contracts.domain import DomainDefinition
from corpussieve.contracts.intent import (
    BoundaryQuestion,
    BoundaryQuestionsList,
    FacetProposal,
)
from corpussieve.domain.prompts.intent_v1 import (
    BOUNDARY_SYSTEM_PROMPT,
    FACET_SYSTEM_PROMPT,
)
from corpussieve.models.base import ModelProvider


def propose_facets(
    provider: ModelProvider, model_id: str, intent: str, language: str = "en"
) -> FacetProposal:
    """Generate conceptual facet proposals from high-level text intent."""
    prompt = (
        f"Language: {language}\n"
        f"User Intent: {intent}\n\n"
        "Propose conceptual include_facets and exclude_facets."
    )
    res = provider.complete_structured(
        model_id=model_id,
        schema=FacetProposal,
        system=FACET_SYSTEM_PROMPT,
        prompt=prompt,
    )
    if isinstance(res, FacetProposal):
        return res
    raise ValueError("Provider failed to return FacetProposal")


def propose_boundary_questions(
    provider: ModelProvider,
    model_id: str,
    intent: str,
    facets: FacetProposal,
) -> list[BoundaryQuestion]:
    """Generate up to 8 boundary questions to clarify domain scope."""
    prompt = (
        f"User Intent: {intent}\n"
        f"Include Facets: {', '.join(facets.include_facets)}\n"
        f"Exclude Facets: {', '.join(facets.exclude_facets)}\n\n"
        "Generate up to 8 boundary questions."
    )
    res = provider.complete_structured(
        model_id=model_id,
        schema=BoundaryQuestionsList,
        system=BOUNDARY_SYSTEM_PROMPT,
        prompt=prompt,
    )
    if isinstance(res, BoundaryQuestionsList):
        return res.questions[:8]
    return []


def apply_answers(
    defn: DomainDefinition,
    questions: list[BoundaryQuestion],
    answers: dict[str, str],
) -> DomainDefinition:
    """Fold accepted answers into domain definition facets include/exclude lists."""
    inc = set(defn.facets.include)
    exc = set(defn.facets.exclude)

    for q in questions:
        ans = answers.get(q.id, q.recommended).lower()
        if ans == "include":
            inc.add(q.facet_target)
            exc.discard(q.facet_target)
        elif ans == "exclude":
            exc.add(q.facet_target)
            inc.discard(q.facet_target)

    defn.facets.include = sorted(inc)
    defn.facets.exclude = sorted(exc)
    return defn
