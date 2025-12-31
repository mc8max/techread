from __future__ import annotations


def _build_source_filters(
    *,
    source: list[int] | None,
    tag: list[str] | None,
    today: bool,
    include_read: bool,
    since_iso: str,
) -> tuple[str, list]:
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
