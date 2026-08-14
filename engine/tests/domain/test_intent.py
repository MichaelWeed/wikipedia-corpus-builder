from corpussieve.contracts.domain import DomainDefinition, DomainFacets, DomainRoot
from corpussieve.contracts.intent import BoundaryQuestion
from corpussieve.domain.intent import apply_answers


def test_apply_answers_folding() -> None:
    defn = DomainDefinition(
        id="test",
        name="Test",
        language="en",
        description="d",
        roots=[DomainRoot(query="Category:Test")],
        facets=DomainFacets(include=["video games"], exclude=["board games"]),
    )

    questions = [
        BoundaryQuestion(
            id="q1",
            question="Include mobile games?",
            recommended="include",
            facet_target="mobile games",
        ),
        BoundaryQuestion(
            id="q2",
            question="Include pinball games?",
            recommended="exclude",
            facet_target="pinball games",
        ),
    ]

    answers = {"q1": "include", "q2": "exclude"}
    res = apply_answers(defn, questions, answers)

    assert "mobile games" in res.facets.include
    assert "pinball games" in res.facets.exclude
