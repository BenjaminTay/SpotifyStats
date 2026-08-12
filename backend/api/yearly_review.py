"""Deterministic Yearly Review V2 API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.dependencies import get_yearly_review_context
from backend.models.yearly_review import (
    YearlyReviewAvailableYearsResponse,
    YearlyReviewFilterContext,
    YearlyReviewRecordsPage,
    YearlyReviewResponse,
)
from backend.services.yearly_review_service import (
    get_yearly_review,
    get_yearly_review_available_years,
    get_yearly_review_records,
)

router = APIRouter(prefix="/yearly-review", tags=["Yearly Review V2"])
YearPath = Annotated[int, Path(ge=2000, le=2100, description="报告年份")]


@router.get("/available-years", response_model=YearlyReviewAvailableYearsResponse)
def available_years() -> YearlyReviewAvailableYearsResponse:
    return get_yearly_review_available_years()


@router.get("/{year}", response_model=YearlyReviewResponse)
def yearly_review(
    year: YearPath,
    context: YearlyReviewFilterContext = Depends(get_yearly_review_context),
) -> YearlyReviewResponse:
    return get_yearly_review(year, context)


@router.get("/{year}/records", response_model=YearlyReviewRecordsPage)
def yearly_review_records(
    year: YearPath,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    context: YearlyReviewFilterContext = Depends(get_yearly_review_context),
) -> YearlyReviewRecordsPage:
    return get_yearly_review_records(
        year,
        context,
        page=page,
        page_size=page_size,
    )
