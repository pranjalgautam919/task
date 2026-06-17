"""Pagination helper utilities."""

from typing import TypeVar, Generic, List
import math


def paginate_query_params(page: int, page_size: int, total_count: int) -> dict:
    """
    Calculate pagination metadata.

    Args:
        page: Current page number (1-indexed)
        page_size: Number of items per page
        total_count: Total number of items

    Returns:
        Dictionary with pagination metadata
    """
    total_pages = math.ceil(total_count / page_size) if page_size > 0 else 0
    offset = (page - 1) * page_size

    return {
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "total_pages": total_pages,
        "offset": offset,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }
