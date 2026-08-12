from __future__ import annotations

from backend.api import yearly_review as yearly_review_api
from backend.models.yearly_review import (
    YearlyBillboardCoverage,
    YearlyComparisonCoverage,
    YearlyPlayCoverage,
    YearlyReviewAvailableYearsResponse,
    YearlyReviewCoverage,
    YearlyReviewRecordsPage,
    YearlyReviewResponse,
    YearlyTasteCoverage,
)


def _empty_response(year, context) -> YearlyReviewResponse:
    coverage = YearlyReviewCoverage(
        status="empty",
        play=YearlyPlayCoverage(status="empty"),
        billboard=YearlyBillboardCoverage(status="empty", source_status="empty"),
        comparison=YearlyComparisonCoverage(reason="baseline_unavailable"),
        taste=YearlyTasteCoverage(),
    )
    return YearlyReviewResponse(
        year=year,
        status="empty",
        filter_context=context,
        coverage=coverage,
    )


def test_available_years_has_response_model_and_request_id(client, monkeypatch) -> None:
    monkeypatch.setattr(
        yearly_review_api,
        "get_yearly_review_available_years",
        lambda: YearlyReviewAvailableYearsResponse(years=[2023, 2024, 2025], latest_year=2025),
    )

    response = client.get(
        "/api/yearly-review/available-years",
        headers={"X-Request-ID": "yearly-contract"},
    )

    assert response.status_code == 200
    assert response.json() == {"years": [2023, 2024, 2025], "latest_year": 2025}
    assert response.headers["X-Request-ID"] == "yearly-contract"


def test_empty_year_returns_legal_v2_payload(client, monkeypatch) -> None:
    monkeypatch.setattr(
        yearly_review_api,
        "get_yearly_review",
        lambda year, context: _empty_response(year, context),
    )

    response = client.get("/api/yearly-review/2099")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "yearly_review_v2"
    assert payload["year"] == 2099
    assert payload["status"] == "empty"
    assert payload["records"]["featured"] == []
    assert payload["methodology"]["content_version"] == "yearly_review_v2_6"
    assert payload["filter_context"]["filter_fingerprint"]


def test_records_endpoint_is_server_paginated(client, monkeypatch) -> None:
    def fake_records(year, context, *, page, page_size):
        return YearlyReviewRecordsPage(
            content_version="yearly_review_v2_6",
            year=year,
            filter_fingerprint=context.filter_fingerprint,
            page=page,
            page_size=page_size,
            total=120,
            total_pages=3,
            items=[],
            catalog_counts={"input_total": 120},
        )

    monkeypatch.setattr(yearly_review_api, "get_yearly_review_records", fake_records)
    response = client.get("/api/yearly-review/2025/records?page=2&page_size=50")

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 2
    assert payload["page_size"] == 50
    assert payload["total"] == 120
    assert payload["total_pages"] == 3
    assert payload["content_version"] == "yearly_review_v2_6"


def test_invalid_year_and_pagination_return_structured_422(client) -> None:
    invalid_year = client.get("/api/yearly-review/1999")
    invalid_page = client.get("/api/yearly-review/2025/records?page=0")
    invalid_page_size = client.get("/api/yearly-review/2025/records?page_size=101")

    assert invalid_year.status_code == 422
    assert invalid_page.status_code == 422
    assert invalid_page_size.status_code == 422
    assert isinstance(invalid_year.json()["detail"], list)
    assert isinstance(invalid_page.json()["detail"], list)
    assert isinstance(invalid_page_size.json()["detail"], list)
