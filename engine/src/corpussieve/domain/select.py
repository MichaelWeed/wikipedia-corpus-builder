from corpussieve.contracts.domain import DomainDefinition
from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.manifest import ManifestRecord, SelectionReason
from corpussieve.domain.traverse import TraversalResult
from corpussieve.metadata.queries import MetadataIndex
from corpussieve.metadata.rows import PageRow
from corpussieve.metadata.titles import normalize_title


def select_articles(
    index: MetadataIndex,
    traversal: TraversalResult,
    defn: DomainDefinition,
) -> tuple[list[ManifestRecord], list[str]]:
    """Select target namespace-0 articles from traversed categories and generate ManifestRecords."""
    warnings: list[str] = list(traversal.warnings)
    policy = defn.policy

    # Build lookup: cat -> (root_query, depth)
    cat_info: dict[str, tuple[str, int]] = {}
    for dec in traversal.decisions:
        if dec.category in traversal.included and dec.depth is not None and dec.root is not None:
            root_q = dec.root
            if dec.category not in cat_info or dec.depth < cat_info[dec.category][1]:
                cat_info[dec.category] = (root_q, dec.depth)

    # Map candidate page_id -> min score (depth, cat, root_q)
    page_provenance: dict[int, tuple[int, str, str]] = {}

    for cat in traversal.included:
        info = cat_info.get(cat, ("Category:Unknown", 999999))
        root_q, depth = info
        pids = index.member_page_ids(cat, namespaces=(0,))
        for pid in pids:
            score = (depth, cat, root_q)
            if pid not in page_provenance or (depth, cat) < (
                page_provenance[pid][0],
                page_provenance[pid][1],
            ):
                page_provenance[pid] = score

    all_pids = list(page_provenance.keys())
    page_rows: list[PageRow] = index.pages_by_ids(all_pids)
    pid_to_row: dict[int, PageRow] = {p.page_id: p for p in page_rows}

    norm_hard_exclude = {normalize_title(t) for t in defn.hard_exclude_pages if t.strip()}
    norm_forced_include = {normalize_title(t) for t in defn.forced_include_pages if t.strip()}

    collisions = norm_forced_include & norm_hard_exclude
    for col in sorted(collisions):
        warnings.append(f"exclude_overrides_force:{col}")

    records: dict[int, ManifestRecord] = {}

    for pid, (depth, via_cat, root_q) in page_provenance.items():
        row = pid_to_row.get(pid)
        if not row:
            continue

        if row.page_is_redirect and not policy.include_redirects:
            continue

        if row.page_title in norm_hard_exclude:
            continue

        records[pid] = ManifestRecord(
            project=defn.id,
            language=defn.language,
            page_id=pid,
            title=row.page_title,
            namespace=row.page_namespace,
            selected=True,
            selection=SelectionReason(
                root=root_q,
                depth=depth,
                via_category=via_cat,
                reason_type="category_path",
            ),
        )

    for forced_title in sorted(norm_forced_include):
        if forced_title in norm_hard_exclude:
            continue

        p_row = index.page_by_title(forced_title)
        if not p_row:
            warnings.append(f"forced_include_unresolved:{forced_title}")
            continue

        if p_row.page_namespace != 0:
            continue

        if p_row.page_is_redirect and not policy.include_redirects:
            continue

        records[p_row.page_id] = ManifestRecord(
            project=defn.id,
            language=defn.language,
            page_id=p_row.page_id,
            title=p_row.page_title,
            namespace=p_row.page_namespace,
            selected=True,
            selection=SelectionReason(
                root=f"Category:{forced_title}",
                depth=0,
                via_category=forced_title,
                reason_type="forced_include",
            ),
        )

    sorted_records = sorted(records.values(), key=lambda r: r.page_id)

    if len(sorted_records) > policy.max_total_articles:
        msg = (
            f"Selected articles count ({len(sorted_records)}) exceeds "
            f"max limit of {policy.max_total_articles}."
        )
        raise CorpusSieveError(
            ErrorCode.DOMAIN_RUNAWAY_GROWTH,
            msg,
            detail={
                "count": len(sorted_records),
                "limit": policy.max_total_articles,
            },
        )

    return sorted_records, warnings
