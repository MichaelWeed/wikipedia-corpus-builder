from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from corpussieve.contracts.domain import DomainDefinition
from corpussieve.contracts.enums import (
    AmbiguousBranchPolicy,
    BranchDecision,
    SelectionMode,
)
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.lock import CategoryDecision
from corpussieve.domain.resolve import ResolvedRoot
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.metadata.titles import normalize_title


@dataclass(frozen=True)
class AmbiguousBranchContext:
    defn: DomainDefinition
    root: ResolvedRoot
    parent_path: list[str]
    candidate: str
    sample_children: list[str]
    sample_members: list[str]


AmbiguousHook = Callable[[AmbiguousBranchContext], BranchDecision]


@dataclass
class TraversalResult:
    decisions: list[CategoryDecision] = field(default_factory=list)
    included: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    expanded_count: int = 0


def traverse(
    index: MetadataIndex,
    resolved_roots: list[ResolvedRoot],
    explicit_excluded: set[str],
    facet_excluded: set[str],
    defn: DomainDefinition,
    on_ambiguous: AmbiguousHook | None = None,
) -> TraversalResult:
    """BFS category graph traversal engine with determinism, cycle safety, and runaway guards."""
    decisions: list[CategoryDecision] = []
    included: set[str] = set()
    warnings: list[str] = []
    visited: dict[str, tuple[str, int]] = {}  # cat -> (root_query, depth)
    expanded_categories: list[str] = []
    expanded_count = 0

    all_excluded = explicit_excluded | facet_excluded
    policy = defn.policy

    norm_include_facets = [normalize_title(f).lower() for f in defn.facets.include if f.strip()]

    for root in resolved_roots:
        root_cat = root.category
        if root_cat in visited:
            continue

        queue: deque[tuple[str, int, list[str]]] = deque([(root_cat, 0, [root_cat])])
        visited[root_cat] = (root.query, 0)

        decisions.append(
            CategoryDecision(
                category=root_cat,
                decision=BranchDecision.INCLUDE,
                confidence=1.0,
                reason="Root category",
                root=f"Category:{root_cat}",
                depth=0,
                source="traversal",
            )
        )
        included.add(root_cat)

        while queue:
            current_cat, depth, path = queue.popleft()

            if len(included) > policy.max_total_categories:
                last_20 = expanded_categories[-20:]
                msg = (
                    f"Category traversal exceeded maximum limit of "
                    f"{policy.max_total_categories} categories."
                )
                raise CorpusSieveError(
                    ErrorCode.DOMAIN_RUNAWAY_GROWTH,
                    msg,
                    detail={"last_expanded": last_20},
                )

            if depth >= root.max_depth:
                continue

            expanded_count += 1
            expanded_categories.append(current_cat)

            raw_children = index.child_categories(current_cat)
            if len(raw_children) > 5000:
                warnings.append(f"explosive_growth:{current_cat}")

            normalized_children: list[str] = []
            for child in raw_children:
                norm = normalize_title(child)
                c_name = norm[9:] if norm.startswith("Category:") else norm
                normalized_children.append(c_name)

            sorted_children = sorted(set(normalized_children))

            for child_cat in sorted_children:
                if child_cat in visited:
                    continue

                child_depth = depth + 1

                # 1. Exclusion check
                if child_cat in all_excluded:
                    reason = (
                        "Explicit category exclusion"
                        if child_cat in explicit_excluded
                        else "Facet exclusion match"
                    )
                    decisions.append(
                        CategoryDecision(
                            category=child_cat,
                            decision=BranchDecision.EXCLUDE,
                            confidence=1.0,
                            reason=reason,
                            root=f"Category:{root_cat}",
                            depth=child_depth,
                            source="facet_exclude" if child_cat in facet_excluded else "traversal",
                        )
                    )
                    visited[child_cat] = (root.query, child_depth)
                    continue

                # 2. Include facet check
                child_lower = child_cat.lower()
                is_facet_matched = any(f in child_lower for f in norm_include_facets)

                source_val: Literal["traversal", "facet_exclude", "llm", "human"] = "traversal"

                if is_facet_matched:
                    decision_val = BranchDecision.INCLUDE
                    reason_val = "Matched include facet"
                    source_val = "traversal"
                else:
                    # 3. Ambiguous branch resolution
                    if policy.ambiguous_branch == AmbiguousBranchPolicy.INCLUDE:
                        decision_val = BranchDecision.INCLUDE
                        reason_val = "Auto-included by policy"
                        source_val = "traversal"
                    elif policy.ambiguous_branch == AmbiguousBranchPolicy.EXCLUDE:
                        decision_val = BranchDecision.EXCLUDE
                        reason_val = "Auto-excluded by policy"
                        source_val = "traversal"
                    else:
                        # REVIEW policy mode
                        if on_ambiguous:
                            sample_children = index.child_categories(child_cat)[:10]
                            sample_members = [
                                str(pid) for pid in index.member_page_ids(child_cat)[:10]
                            ]
                            ctx = AmbiguousBranchContext(
                                defn=defn,
                                root=root,
                                parent_path=path,
                                candidate=child_cat,
                                sample_children=sample_children,
                                sample_members=sample_members,
                            )
                            decision_val = on_ambiguous(ctx)
                            reason_val = "Resolved by ambiguous branch hook"
                            source_val = "llm"
                        else:
                            # Default mode-based policy hook
                            if policy.mode == SelectionMode.HIGH_RECALL:
                                decision_val = BranchDecision.INCLUDE
                                reason_val = "High recall policy default"
                                source_val = "traversal"
                            elif policy.mode == SelectionMode.BALANCED:
                                decision_val = BranchDecision.INCLUDE
                                reason_val = "Balanced policy default"
                                source_val = "traversal"
                                warnings.append(f"unreviewed_branch:{child_cat}")
                            else:  # HIGH_PRECISION
                                decision_val = BranchDecision.EXCLUDE
                                reason_val = "High precision policy default"
                                source_val = "traversal"

                visited[child_cat] = (root.query, child_depth)
                decisions.append(
                    CategoryDecision(
                        category=child_cat,
                        decision=decision_val,
                        confidence=1.0 if is_facet_matched else 0.8,
                        reason=reason_val,
                        root=f"Category:{root_cat}",
                        depth=child_depth,
                        source=source_val,
                    )
                )

                if decision_val == BranchDecision.INCLUDE:
                    included.add(child_cat)
                    queue.append((child_cat, child_depth, path + [child_cat]))

    stats = {
        "roots_count": len(resolved_roots),
        "included_count": len(included),
        "decisions_count": len(decisions),
        "expanded_count": expanded_count,
    }

    return TraversalResult(
        decisions=decisions,
        included=included,
        warnings=warnings,
        stats=stats,
        expanded_count=expanded_count,
    )
