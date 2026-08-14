from dataclasses import dataclass, field

from corpussieve.contracts.domain import DomainDefinition
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.metadata.queries import CategoryHit, MetadataIndex
from corpussieve.metadata.titles import normalize_title


@dataclass(frozen=True)
class ResolvedRoot:
    query: str
    category: str
    max_depth: int


@dataclass(frozen=True)
class RootResolution:
    resolved: list[ResolvedRoot] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    candidates: dict[str, list[CategoryHit]] = field(default_factory=dict)


def resolve_roots(defn: DomainDefinition, index: MetadataIndex) -> RootResolution:
    """Resolve domain definition root category queries against local SQLite metadata index.

    Rule (FR-012): Exact normalized category match only. Unresolved roots raise
    DOMAIN_ROOT_UNRESOLVED with fuzzy candidates attached.
    """
    resolved: list[ResolvedRoot] = []
    unresolved: list[str] = []
    candidates: dict[str, list[CategoryHit]] = {}

    for root_spec in defn.roots:
        raw_query = root_spec.query
        normalized = normalize_title(raw_query)

        # Handle optional Category: prefix in query
        cat_name = normalized[9:] if normalized.startswith("Category:") else normalized

        if index.category_exists(cat_name):
            resolved.append(
                ResolvedRoot(
                    query=raw_query,
                    category=cat_name,
                    max_depth=root_spec.max_depth,
                )
            )
        elif index.category_exists(normalized):
            resolved.append(
                ResolvedRoot(
                    query=raw_query,
                    category=normalized,
                    max_depth=root_spec.max_depth,
                )
            )
        else:
            unresolved.append(raw_query)
            search_hits = index.search_categories(cat_name, limit=10)
            candidates[raw_query] = search_hits

    if unresolved:
        cand_serialized = {q: [h.category for h in hits] for q, hits in candidates.items()}
        raise CorpusSieveError(
            ErrorCode.DOMAIN_ROOT_UNRESOLVED,
            f"Failed to resolve {len(unresolved)} root categories: {', '.join(unresolved)}",
            detail={"unresolved": unresolved, "candidates": cand_serialized},
        )

    return RootResolution(resolved=resolved, unresolved=[], candidates={})


def resolve_exclusions(defn: DomainDefinition, index: MetadataIndex) -> tuple[set[str], set[str]]:
    """Resolve explicit excluded categories and facet-derived excluded category sets.

    Returns:
      (explicit_excluded, facet_excluded)
    """
    explicit_excluded: set[str] = set()
    for cat in defn.exclude_categories:
        norm = normalize_title(cat)
        cat_name = norm[9:] if norm.startswith("Category:") else norm
        if index.category_exists(cat_name):
            explicit_excluded.add(cat_name)
        elif index.category_exists(norm):
            explicit_excluded.add(norm)
        else:
            explicit_excluded.add(cat_name)

    facet_excluded: set[str] = set()
    for exclude_facet in defn.facets.exclude:
        norm_facet = normalize_title(exclude_facet).lower()
        if not norm_facet:
            continue
        # Find category titles containing norm_facet substring
        hits = index.search_categories(norm_facet, limit=500)
        for h in hits:
            if norm_facet in h.category.lower():
                facet_excluded.add(h.category)

    return explicit_excluded, facet_excluded
