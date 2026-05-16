import math
import typing


def paginate_queryset(qs, page: int = 1, page_size: int = 10):
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    count = qs.count()
    total_pages = max(1, math.ceil(count / page_size)) if count else 1
    if page > total_pages:
        page = total_pages
    start = (page - 1) * page_size
    end = start + page_size
    return {
        'count': count,
        'page': page,
        'total_pages': total_pages,
        'next': str(page + 1) if page < total_pages else None,
        'previous': str(page - 1) if page > 1 else None,
        'results': list(qs[start:end]),
    }
