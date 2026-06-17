"""
Mock paginated APIs for Customers, Orders, and Refunds.

These endpoints serve data from PostgreSQL with full pagination support.
They simulate external data source APIs that the ingestion service pulls from.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Customer, Order, Refund
from app.schemas import (
    CustomerResponse, OrderResponse, RefundResponse, PaginatedResponse,
)
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/mock", tags=["Mock APIs"])


@router.get("/customers", response_model=PaginatedResponse[CustomerResponse])
async def get_customers(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(
        1000, ge=1, le=5000, description="Items per page"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated list of customers."""
    # Get total count
    count_result = await db.execute(select(func.count(Customer.id)))
    total_count = count_result.scalar_one()

    if total_count == 0:
        return PaginatedResponse(
            data=[], page=page, page_size=page_size,
            total_count=0, total_pages=0,
        )

    # Calculate pagination
    total_pages = (total_count + page_size - 1) // page_size
    if page > total_pages:
        raise HTTPException(
            status_code=404,
            detail=f"Page {page} not found. Total pages: {total_pages}",
        )

    offset = (page - 1) * page_size

    # Fetch data
    result = await db.execute(
        select(Customer)
        .order_by(Customer.created_at)
        .offset(offset)
        .limit(page_size)
    )
    customers = result.scalars().all()

    return PaginatedResponse(
        data=[CustomerResponse.model_validate(c) for c in customers],
        page=page,
        page_size=page_size,
        total_count=total_count,
        total_pages=total_pages,
    )


@router.get("/orders", response_model=PaginatedResponse[OrderResponse])
async def get_orders(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(
        1000, ge=1, le=5000, description="Items per page"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated list of orders."""
    count_result = await db.execute(select(func.count(Order.id)))
    total_count = count_result.scalar_one()

    if total_count == 0:
        return PaginatedResponse(
            data=[], page=page, page_size=page_size,
            total_count=0, total_pages=0,
        )

    total_pages = (total_count + page_size - 1) // page_size
    if page > total_pages:
        raise HTTPException(
            status_code=404,
            detail=f"Page {page} not found. Total pages: {total_pages}",
        )

    offset = (page - 1) * page_size

    result = await db.execute(
        select(Order)
        .order_by(Order.order_date)
        .offset(offset)
        .limit(page_size)
    )
    orders = result.scalars().all()

    return PaginatedResponse(
        data=[OrderResponse.model_validate(o) for o in orders],
        page=page,
        page_size=page_size,
        total_count=total_count,
        total_pages=total_pages,
    )


@router.get("/refunds", response_model=PaginatedResponse[RefundResponse])
async def get_refunds(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(
        1000, ge=1, le=5000, description="Items per page"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Get paginated list of refunds."""
    count_result = await db.execute(select(func.count(Refund.id)))
    total_count = count_result.scalar_one()

    if total_count == 0:
        return PaginatedResponse(
            data=[], page=page, page_size=page_size,
            total_count=0, total_pages=0,
        )

    total_pages = (total_count + page_size - 1) // page_size
    if page > total_pages:
        raise HTTPException(
            status_code=404,
            detail=f"Page {page} not found. Total pages: {total_pages}",
        )

    offset = (page - 1) * page_size

    result = await db.execute(
        select(Refund)
        .order_by(Refund.refund_date)
        .offset(offset)
        .limit(page_size)
    )
    refunds = result.scalars().all()

    return PaginatedResponse(
        data=[RefundResponse.model_validate(r) for r in refunds],
        page=page,
        page_size=page_size,
        total_count=total_count,
        total_pages=total_pages,
    )
