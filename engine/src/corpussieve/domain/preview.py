import random
from collections import defaultdict
from collections.abc import Sequence

from corpussieve.contracts.domain import DomainDefinition
from corpussieve.contracts.lock import DomainLock
from corpussieve.contracts.manifest import ManifestRecord
from corpussieve.contracts.preview import DomainPreview, ExplainResult
from corpussieve.domain.traverse import TraversalResult
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.metadata.titles import normalize_title

EST_BYTES_PER_ARTICLE = 3500


def build_preview(
    index: MetadataIndex,
    lock: DomainLock,
    traversal: TraversalResult,
    records: Sequence[ManifestRecord],
    defn: DomainDefinition,
) -> DomainPreview:
    """Build summary domain preview analysis and diagnostic metrics."""
    article_count = len(records)
    estimated_bytes = article_count * EST_BYTES_PER_ARTICLE

    counts_by_root: dict[str, int] = defaultdict(int)
    counts_by_depth: dict[int, int] = defaultdict(int)
    sample_borderline: list[str] = []

    # Map root query -> max_depth
    root_max_depths = {r.query: r.max_depth for r in lock.resolved_roots}

    for rec in records:
        counts_by_root[rec.selection.root] += 1
        counts_by_depth[rec.selection.depth] += 1

        max_d = root_max_depths.get(rec.selection.root, 999)
        if rec.selection.depth == max_d:
            sample_borderline.append(rec.title)

    # Deterministic sample included (seeded by lock_hash)
    seed_val = int(lock.lock_hash[:8], 16)
    all_titles = sorted(r.title for r in records)
    rng = random.Random(seed_val)
    sample_included = rng.sample(all_titles, min(10, len(all_titles)))

    # Contamination groups check
    contamination_groups: dict[str, list[str]] = defaultdict(list)
    for facet in defn.facets.exclude:
        norm_f = normalize_title(facet).lower()
        if not norm_f:
            continue
        for dec in lock.category_decisions:
            if dec.decision == "include" and norm_f in dec.category.lower():
                contamination_groups[facet].append(dec.category)

    warnings: list[str] = list(traversal.warnings)
    stats = index.stats()
    total_ns0 = stats.page_count

    if total_ns0 > 0 and article_count > (total_ns0 * 0.5):
        warnings.append("selection_too_broad")
    if article_count < 5:
        warnings.append("selection_probably_incomplete")

    return DomainPreview(
        article_count=article_count,
        estimated_output_bytes=estimated_bytes,
        counts_by_root=dict(counts_by_root),
        counts_by_depth=dict(counts_by_depth),
        sample_included=sample_included,
        sample_borderline=sample_borderline[:10],
        contamination_groups=dict(contamination_groups),
        warnings=warnings,
    )


def explain_page(
    index: MetadataIndex,
    lock: DomainLock,
    records: Sequence[ManifestRecord],
    title_or_id: str | int,
    defn: DomainDefinition,
) -> ExplainResult:
    """Explain why a specific page or article is included, excluded, or absent."""
    # Find matching record in manifest
    target_str = str(title_or_id)
    if isinstance(title_or_id, int):
        rec = next((r for r in records if r.page_id == title_or_id), None)
    else:
        norm_target = normalize_title(title_or_id)
        rec = next((r for r in records if r.title == norm_target), None)

    if rec:
        return ExplainResult(
            target=rec.title,
            status="included",
            provenance_chain=[rec.selection.root, rec.selection.via_category],
            reason=f"Selected via {rec.selection.reason_type} at depth {rec.selection.depth}",
        )

    # Page not in selected records: query page details
    if isinstance(title_or_id, int):
        p_rows = index.pages_by_ids([title_or_id])
        p_row = p_rows[0] if p_rows else None
    else:
        p_row = index.page_by_title(title_or_id)

    if not p_row:
        return ExplainResult(
            target=target_str,
            status="absent",
            provenance_chain=[],
            reason="Page does not exist in metadata database index",
        )

    # Check hard exclude
    norm_hard_exclude = {normalize_title(t) for t in defn.hard_exclude_pages if t.strip()}
    if p_row.page_title in norm_hard_exclude:
        return ExplainResult(
            target=p_row.page_title,
            status="excluded",
            provenance_chain=[],
            reason="Hard excluded in domain definition",
        )

    # Check category assignments for excluded categories
    assigned_cats = index.categories_of_page(p_row.page_id)
    decisions_map = {d.category: d for d in lock.category_decisions}

    for cat in assigned_cats:
        norm_cat = normalize_title(cat)
        c_name = norm_cat[9:] if norm_cat.startswith("Category:") else norm_cat
        dec = decisions_map.get(c_name)
        if dec and dec.decision == "exclude":
            return ExplainResult(
                target=p_row.page_title,
                status="excluded",
                provenance_chain=[dec.root or "", dec.category],
                reason=f"Category '{dec.category}' was excluded ({dec.reason})",
            )

    return ExplainResult(
        target=p_row.page_title,
        status="excluded",
        provenance_chain=[],
        reason="Page categories were not reached during root graph traversal",
    )
