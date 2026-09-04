PER_PAGE = 20


def page_info(total, page, per_page=PER_PAGE):
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    page_range = []
    if total_pages <= 7:
        page_range = list(range(1, total_pages + 1))
    else:
        if page <= 4:
            page_range = list(range(1, 6)) + ["...", total_pages]
        elif page >= total_pages - 3:
            page_range = [1, "..."] + list(range(total_pages - 4, total_pages + 1))
        else:
            page_range = [1, "...", page - 1, page, page + 1, "...", total_pages]

    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "page_range": page_range,
    }


def paginate_sql(sql, params, page, per_page=PER_PAGE):
    page = max(1, page)
    count_sql = f"SELECT COUNT(*) FROM ({sql})"
    offset = (page - 1) * per_page
    data_sql = sql + f" LIMIT {per_page} OFFSET {offset}"
    return count_sql, data_sql, params
