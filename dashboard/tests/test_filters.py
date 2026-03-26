"""Tests for utils.filters — pure DataFrame filtering functions."""

from datetime import date

import pandas as pd
import pytest

from utils.filters import (
    by_application_number,
    by_date,
    by_min_score,
    by_radius,
    by_status,
)


class TestByDate:
    """Tests for filters.by_date."""

    def test_full_range_returns_all(self, sample_applications):
        start = date(2026, 1, 1)
        end = date(2026, 12, 31)
        result = by_date(sample_applications, start, end)
        assert len(result) == len(sample_applications)

    def test_narrow_range_filters_correctly(self, sample_applications):
        start = date(2026, 3, 1)
        end = date(2026, 3, 10)
        result = by_date(sample_applications, start, end)
        assert all(result["date"].dt.date >= start)
        assert all(result["date"].dt.date <= end)
        assert len(result) == 2  # 2026-03-01 and 2026-03-10

    def test_single_day_range(self, sample_applications):
        day = date(2026, 3, 1)
        result = by_date(sample_applications, day, day)
        assert len(result) == 1
        assert result.iloc[0]["application_id"] == "th-2026-001"

    def test_range_with_no_matches_returns_empty(self, sample_applications):
        start = date(2025, 1, 1)
        end = date(2025, 12, 31)
        result = by_date(sample_applications, start, end)
        assert result.empty

    def test_boundary_dates_are_inclusive(self, sample_applications):
        # Earliest date in fixture is 2026-01-20, latest is 2026-03-10
        start = date(2026, 1, 20)
        end = date(2026, 1, 20)
        result = by_date(sample_applications, start, end)
        assert len(result) == 1
        assert result.iloc[0]["application_id"] == "th-2026-005"


class TestByStatus:
    """Tests for filters.by_status."""

    def test_all_returns_full_dataframe(self, sample_applications):
        result = by_status(sample_applications, "All")
        assert len(result) == len(sample_applications)

    def test_specific_status_filters(self, sample_applications):
        result = by_status(sample_applications, "Approved")
        assert len(result) == 1
        assert all(result["status"] == "Approved")

    def test_pending_decision_returns_two(self, sample_applications):
        result = by_status(sample_applications, "Pending Decision")
        assert len(result) == 2

    def test_nonexistent_status_returns_empty(self, sample_applications):
        result = by_status(sample_applications, "Withdrawn")
        assert result.empty

    def test_status_match_is_exact(self, sample_applications):
        result = by_status(sample_applications, "Pending")
        assert result.empty  # Must be "Pending Decision", not just "Pending"


class TestByMinScore:
    """Tests for filters.by_min_score."""

    def test_min_score_1_returns_all(self, sample_applications):
        result = by_min_score(sample_applications, 1)
        assert len(result) == len(sample_applications)

    def test_min_score_5_returns_only_top(self, sample_applications):
        result = by_min_score(sample_applications, 5)
        assert all(result["public_interest_score"] >= 5)
        assert len(result) == 2  # Two apps with score 5

    def test_min_score_4_filters_low_scores(self, sample_applications):
        result = by_min_score(sample_applications, 4)
        assert all(result["public_interest_score"] >= 4)
        assert len(result) == 3  # Two 5s and one 4

    def test_min_score_above_max_returns_empty(self, sample_applications):
        result = by_min_score(sample_applications, 6)
        assert result.empty

    def test_result_preserves_columns(self, sample_applications):
        result = by_min_score(sample_applications, 3)
        assert list(result.columns) == list(sample_applications.columns)


class TestByRadius:
    """Tests for filters.by_radius."""

    def test_large_radius_returns_all(self, sample_applications):
        # Center roughly in Tower Hamlets — 10 miles should cover everything
        result = by_radius(sample_applications, 51.52, -0.05, 10.0)
        assert len(result) == len(sample_applications)

    def test_tiny_radius_returns_subset(self, sample_applications):
        # Very small radius around first app's exact location
        result = by_radius(sample_applications, 51.5248, -0.0345, 0.01)
        assert len(result) >= 1
        assert "th-2026-001" in result["application_id"].values

    def test_zero_radius_returns_empty_or_exact(self, sample_applications):
        result = by_radius(sample_applications, 51.5248, -0.0345, 0.0)
        # Only exact co-located points (haversine=0) would match
        assert len(result) <= 1

    def test_distant_center_returns_empty(self, sample_applications):
        # Edinburgh coordinates — way outside Tower Hamlets
        result = by_radius(sample_applications, 55.9533, -3.1883, 1.0)
        assert result.empty


class TestByApplicationNumber:
    """Tests for filters.by_application_number."""

    def test_exact_match(self, sample_applications):
        result = by_application_number(
            sample_applications, "PA/26/00142/A1"
        )
        assert len(result) == 1
        assert result.iloc[0]["application_id"] == "th-2026-001"

    def test_partial_match(self, sample_applications):
        result = by_application_number(sample_applications, "PA/26")
        assert len(result) == len(sample_applications)

    def test_case_insensitive(self, sample_applications):
        result = by_application_number(sample_applications, "pa/26/00142/a1")
        assert len(result) == 1

    def test_no_match_returns_empty(self, sample_applications):
        result = by_application_number(sample_applications, "ZZZZ")
        assert result.empty

    def test_empty_query_returns_all(self, sample_applications):
        result = by_application_number(sample_applications, "")
        assert len(result) == len(sample_applications)

    def test_suffix_match(self, sample_applications):
        result = by_application_number(sample_applications, "FUL")
        ful_count = sample_applications["application_number"].str.contains(
            "FUL", case=False
        ).sum()
        assert len(result) == ful_count
