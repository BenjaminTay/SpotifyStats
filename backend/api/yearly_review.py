"""Deterministic Yearly Review V2 API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status

from backend.core.access_surface import is_public_readonly
from backend.dependencies import get_yearly_review_context
from backend.models.yearly_review import (
    YearlyReviewAvailableYearsResponse,
    YearlyReviewFilterContext,
    YearlyReviewGenerationResponse,
    YearlyReviewPrewarmRequest,
    YearlyReviewRecordsPage,
    YearlyReviewResponse,
)
from backend.services.yearly_review_generation import YearlyReviewGenerationTimeoutError
from backend.services.yearly_review_service import (
    get_cached_yearly_review,
    get_cached_yearly_review_records,
    get_yearly_review,
    get_yearly_review_available_years,
    get_yearly_review_generation_status,
    get_yearly_review_records,
    prewarm_yearly_reviews,
)

router = APIRouter(prefix="/yearly-review", tags=["Yearly Review V2"])
YearPath = Annotated[int, Path(ge=2000, le=2100, description="报告年份")]


@router.get("/available-years", response_model=YearlyReviewAvailableYearsResponse)
def available_years() -> YearlyReviewAvailableYearsResponse:
    return get_yearly_review_available_years()


@router.post(
    "/prewarm",
    response_model=YearlyReviewGenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def prewarm(
    request: YearlyReviewPrewarmRequest,
    context: YearlyReviewFilterContext = Depends(get_yearly_review_context),
) -> YearlyReviewGenerationResponse:
    try:
        return prewarm_yearly_reviews(
            request.years,
            context,
            foreground_year=request.foreground_year,
        )
    except ValueError as exc:
        if str(exc).startswith("unavailable_years:"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="只能生成当前数据中存在的年份",
            ) from exc
        raise


@router.get("/generation-status", response_model=YearlyReviewGenerationResponse)
def generation_status(
    years: Annotated[
        str | None,
        Query(description="可选的逗号分隔报告年份；省略时返回全部可用年份"),
    ] = None,
    context: YearlyReviewFilterContext = Depends(get_yearly_review_context),
) -> YearlyReviewGenerationResponse:
    parsed_years: list[int] | None = None
    if years:
        try:
            parsed_years = list(dict.fromkeys(int(value) for value in years.split(",")))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="years 必须是逗号分隔的整数年份",
            ) from exc
        if any(year < 2000 or year > 2100 for year in parsed_years):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="years 必须位于 2000 到 2100 之间",
            )
    return get_yearly_review_generation_status(context, years=parsed_years)


@router.get("/{year}", response_model=YearlyReviewResponse)
def yearly_review(
    request: Request,
    year: YearPath,
    context: YearlyReviewFilterContext = Depends(get_yearly_review_context),
) -> YearlyReviewResponse:
    if is_public_readonly(request):
        cached = get_cached_yearly_review(year, context)
        if cached is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="年度总结尚未由管理入口生成",
            )
        return cached
    try:
        return get_yearly_review(year, context)
    except YearlyReviewGenerationTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="年度总结仍在后台生成，请稍后重试",
        ) from exc


@router.get("/{year}/records", response_model=YearlyReviewRecordsPage)
def yearly_review_records(
    request: Request,
    year: YearPath,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    context: YearlyReviewFilterContext = Depends(get_yearly_review_context),
) -> YearlyReviewRecordsPage:
    if is_public_readonly(request):
        cached = get_cached_yearly_review_records(
            year,
            context,
            page=page,
            page_size=page_size,
        )
        if cached is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="年度总结尚未由管理入口生成",
            )
        return cached
    return get_yearly_review_records(
        year,
        context,
        page=page,
        page_size=page_size,
    )
