from __future__ import annotations


def _build_source_filters(
    *,
    source: list[int] | None,
    tag: list[str] | None,
    today: bool,
    include_read: bool,
    since_iso: str,
) -> tuple[str, list]:
    """Build SQL WHERE clause and parameters for filtering sources.

    This function constructs a SQL WHERE clause and corresponding parameter list
    based on various filter criteria for sources. It supports filtering by:
    - Publication date (today only)
    - Read state
    - Source IDs
    - Tag names and tags

    Args:
        source: List of source IDs to filter by. If None or empty, no source filtering is applied.
        tag: List of tag terms to filter by. If None or empty, no tag filtering is applied.
        today: If True, filters for items published today (using since_iso).
        include_read: If False, excludes items with read_state = 'read'.
        since_iso: ISO format date string for filtering by publication date.

    Returns:
        tuple[str, list]: A tuple containing:
            - where_sql: The SQL WHERE clause (empty string if no filters applied)
            - params: List of parameters to be used with the WHERE clause

    Example:
        where_sql, params = _build_source_filters(
            source=[1, 2, 3],
            tag=["tech", "python"],
            today=True,
            include_read=False,
            since_iso="2023-01-01"
        )
    """
    where = []
    params: list = []
    if today:
        where.append("p.published_at >= ?")
        params.append(since_iso)
    if not include_read:
        where.append("p.read_state != 'read'")
    source_ids = [int(s) for s in (source or [])]
    if source_ids:
        placeholders = ",".join("?" for _ in source_ids)
        where.append(f"s.id IN ({placeholders})")
        params.extend(source_ids)
    tag_terms = [str(t).strip().lower() for t in (tag or []) if str(t).strip()]
    if tag_terms:
        clauses = []
        for t in tag_terms:
            clauses.append("(lower(s.name) LIKE ? OR lower(s.tags) LIKE ?)")
            like = f"%{t}%"
            params.extend([like, like])
        where.append("(" + " OR ".join(clauses) + ")")
    where_sql = " AND ".join(where)
    if where_sql:
        where_sql = "WHERE " + where_sql
    return where_sql, params
