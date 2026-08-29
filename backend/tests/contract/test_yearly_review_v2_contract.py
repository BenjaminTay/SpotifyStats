from __future__ import annotations

from datetime import datetime, timezone

from backend.api import yearly_review as yearly_review_api
from backend.models.yearly_review import (
    YearlyBillboardCoverage,
    YearlyComparisonCoverage,
    YearlyPlayCoverage,
    YearlyReviewAvailableYearsResponse,
    YearlyReviewCoverage,
    YearlyReviewGenerationResponse,
    YearlyReviewGenerationTask,
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
    assert payload["methodology"]["content_version"] == "yearly_review_v2_16"
    assert payload["filter_context"]["filter_fingerprint"]


def test_prewarm_and_generation_status_have_stable_contract(client, monkeypatch) -> None:
    now = datetime.now(timezone.utc)

    def response(years):
        return YearlyReviewGenerationResponse(
            tasks=[
                YearlyReviewGenerationTask(
                    year=year,
                    state="running" if year == 2025 else "queued",
                    requested_at=now,
                    started_at=now if year == 2025 else None,
                )
                for year in years
            ]
        )

    monkeypatch.setattr(
        yearly_review_api,
        "prewarm_yearly_reviews",
        lambda years, context, *, foreground_year: response(years),
    )
    monkeypatch.setattr(
        yearly_review_api,
        "get_yearly_review_generation_status",
        lambda context, *, years: response(years or [2023, 2024, 2025]),
    )

    accepted = client.post(
        "/api/yearly-review/prewarm",
        json={"years": [2023, 2024, 2025], "foreground_year": 2025},
    )
    status_response = client.get("/api/yearly-review/generation-status?years=2023,2025")

    assert accepted.status_code == 202
    assert accepted.json()["protocol_version"] == "yearly_review_generation_v1"
    assert [task["year"] for task in accepted.json()["tasks"]] == [2023, 2024, 2025]
    assert accepted.json()["tasks"][-1]["started_at"] is not None
    assert status_response.status_code == 200
    assert [task["year"] for task in status_response.json()["tasks"]] == [2023, 2025]


def test_generation_endpoints_validate_years(client) -> None:
    invalid_body = client.post(
        "/api/yearly-review/prewarm",
        json={"years": [1999], "foreground_year": 1999},
    )
    invalid_query = client.get("/api/yearly-review/generation-status?years=2024,not-a-year")

    assert invalid_body.status_code == 422
    assert isinstance(invalid_body.json()["detail"], list)
    assert invalid_query.status_code == 422
    assert invalid_query.json()["detail"] == "years 必须是逗号分隔的整数年份"


def test_prewarm_rejects_year_without_playback_data(client, monkeypatch) -> None:
    def reject(*_args, **_kwargs):
        raise ValueError("unavailable_years:2099")

    monkeypatch.setattr(yearly_review_api, "prewarm_yearly_reviews", reject)
    response = client.post(
        "/api/yearly-review/prewarm",
        json={"years": [2099], "foreground_year": 2099},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "只能生成当前数据中存在的年份"


def test_records_endpoint_keeps_a_curated_compatibility_response(client, monkeypatch) -> None:
    def fake_records(year, context, *, page, page_size):
        return YearlyReviewRecordsPage(
            content_version="yearly_review_v2_16",
            year=year,
            filter_fingerprint=context.filter_fingerprint,
            page=page,
            page_size=page_size,
            total=7,
            total_pages=1,
            items=[],
            catalog_counts={"featured_total": 7},
        )

    monkeypatch.setattr(yearly_review_api, "get_yearly_review_records", fake_records)
    response = client.get("/api/yearly-review/2025/records?page=1&page_size=50")

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 50
    assert payload["total"] == 7
    assert payload["total_pages"] == 1
    assert payload["content_version"] == "yearly_review_v2_16"


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
