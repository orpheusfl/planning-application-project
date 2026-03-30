"""Tests for utils.components — Streamlit UI helpers and formatting."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from utils.components import (
    _score_pill,
    _status_badge,
    build_cluster_map_data,
    get_selected_from_map,
    marker_color,
)
from utils.config import DEFAULT_MARKER_COLOR, SCORE_COLORS, STATUS_CSS_CLASSES


# ── TestStatusBadge ───────────────────────────────────────────────────────


class TestStatusBadge:
    """Tests for components._status_badge."""

    @pytest.mark.parametrize(
        "status, expected_class",
        [
            ("Pending Decision", "status-pending"),
            ("Under Consultation", "status-consultation"),
            ("Approved", "status-approved"),
            ("Refused", "status-refused"),
        ],
    )
    def test_known_statuses_map_to_correct_class(self, status, expected_class):
        html = _status_badge(status)
        assert expected_class in html
        assert status in html

    def test_unknown_status_defaults_to_pending(self):
        html = _status_badge("Withdrawn")
        assert "status-pending" in html
        assert "Withdrawn" in html

    def test_output_is_html_span(self):
        html = _status_badge("Approved")
        assert html.startswith("<span")
        assert html.endswith("</span>")

    def test_case_insensitive_keyword_match(self):
        # "APPROVED" contains "approved" when lowered
        html = _status_badge("APPROVED")
        assert "status-approved" in html


# ── TestScorePill ─────────────────────────────────────────────────────────


class TestScorePill:
    """Tests for components._score_pill."""

    @pytest.mark.parametrize("score", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    def test_valid_scores_produce_html(self, score):
        html = _score_pill(score)
        assert f"score-{score}" in html
        assert str(score) in html

    def test_nan_returns_empty_string(self):
        assert _score_pill(float("nan")) == ""

    def test_none_returns_empty_string(self):
        assert _score_pill(None) == ""

    def test_output_is_html_span(self):
        html = _score_pill(3)
        assert html.startswith("<span")
        assert html.endswith("</span>")

    def test_float_score_is_truncated(self):
        html = _score_pill(4.7)
        assert "score-4" in html
        assert ">4<" in html


# ── TestMarkerColor ───────────────────────────────────────────────────────


class TestMarkerColor:
    """Tests for components.marker_color."""

    @pytest.mark.parametrize("score", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    def test_known_scores_return_score_colors(self, score):
        assert marker_color(score) == SCORE_COLORS[score]

    def test_nan_returns_default(self):
        assert marker_color(float("nan")) == DEFAULT_MARKER_COLOR

    def test_none_returns_default(self):
        assert marker_color(None) == DEFAULT_MARKER_COLOR

    def test_out_of_range_returns_default(self):
        assert marker_color(99) == DEFAULT_MARKER_COLOR

    def test_returns_list_of_four_ints(self):
        color = marker_color(3)
        assert isinstance(color, list)
        assert len(color) == 4
        assert all(isinstance(c, int) for c in color)


# ── TestGetSelectedFromMap ────────────────────────────────────────────────


class TestGetSelectedFromMap:
    """Tests for components.get_selected_from_map (cluster-aware)."""

    @patch("utils.components.st")
    def test_single_marker_returns_application(
        self, mock_st, sample_applications,
    ):
        mock_st.session_state = {}
        cluster_df = build_cluster_map_data(sample_applications)
        single_idx = cluster_df[
            cluster_df["cluster_count"] == 1
        ].index[0]

        event = MagicMock()
        event.selection = {"indices": {"applications": [single_idx]}}

        app, postcode, is_fresh = get_selected_from_map(
            event, cluster_df, sample_applications,
        )

        assert app is not None
        assert postcode is None
        assert is_fresh is True

    @patch("utils.components.st")
    def test_cluster_marker_returns_postcode(
        self, mock_st, sample_applications,
    ):
        mock_st.session_state = {}
        cluster_df = build_cluster_map_data(sample_applications)
        cluster_idx = cluster_df[
            cluster_df["cluster_count"] > 1
        ].index[0]

        event = MagicMock()
        event.selection = {"indices": {"applications": [cluster_idx]}}

        app, postcode, is_fresh = get_selected_from_map(
            event, cluster_df, sample_applications,
        )

        assert app is None
        assert postcode == "E3 4TN"
        assert is_fresh is True

    @patch("utils.components.st")
    def test_no_event_with_persisted_app_falls_back(
        self, mock_st, sample_applications,
    ):
        mock_st.session_state = {"map_selected_app_id": "th-2026-002"}
        cluster_df = build_cluster_map_data(sample_applications)

        app, postcode, is_fresh = get_selected_from_map(
            None, cluster_df, sample_applications,
        )

        assert app is not None
        assert app["application_id"] == "th-2026-002"
        assert postcode is None
        assert is_fresh is False

    @patch("utils.components.st")
    def test_no_event_with_persisted_postcode_falls_back(
        self, mock_st, sample_applications,
    ):
        mock_st.session_state = {"map_selected_postcode": "E3 4TN"}
        cluster_df = build_cluster_map_data(sample_applications)

        app, postcode, is_fresh = get_selected_from_map(
            None, cluster_df, sample_applications,
        )

        assert app is None
        assert postcode == "E3 4TN"
        assert is_fresh is False

    @patch("utils.components.st")
    def test_none_event_no_persisted_returns_none_none(
        self, mock_st, sample_applications,
    ):
        mock_st.session_state = {}
        cluster_df = build_cluster_map_data(sample_applications)

        app, postcode, is_fresh = get_selected_from_map(
            None, cluster_df, sample_applications,
        )

        assert app is None
        assert postcode is None
        assert is_fresh is False

    @patch("utils.components.st")
    def test_filters_changed_ignores_event(
        self, mock_st, sample_applications,
    ):
        mock_st.session_state = {"_filters_changed": True}
        cluster_df = build_cluster_map_data(sample_applications)

        event = MagicMock()
        event.selection = {"indices": {"applications": [0]}}

        app, postcode, is_fresh = get_selected_from_map(
            event, cluster_df, sample_applications,
        )

        assert app is None
        assert postcode is None
        assert is_fresh is False

    @patch("utils.components.st")
    def test_out_of_bounds_index_ignored(
        self, mock_st, sample_applications,
    ):
        mock_st.session_state = {}
        cluster_df = build_cluster_map_data(sample_applications)

        event = MagicMock()
        event.selection = {"indices": {"applications": [999]}}

        app, postcode, is_fresh = get_selected_from_map(
            event, cluster_df, sample_applications,
        )

        assert app is None
        assert postcode is None


# ── TestBuildClusterMapData ───────────────────────────────────────────────


class TestBuildClusterMapData:
    """Tests for components.build_cluster_map_data."""

    def test_groups_by_postcode(self, sample_applications):
        result = build_cluster_map_data(sample_applications)
        # 5 apps across 3 postcodes: E3 4TN (3), E1 6QE (1), E14 0AG (1)
        assert len(result) == 3

    def test_single_app_cluster_has_count_one(self, sample_applications):
        result = build_cluster_map_data(sample_applications)
        singles = result[result["cluster_count"] == 1]
        assert len(singles) == 2

    def test_multi_app_cluster_has_correct_count(self, sample_applications):
        result = build_cluster_map_data(sample_applications)
        e3_cluster = result[result["postcode"] == "E3 4TN"]
        assert e3_cluster.iloc[0]["cluster_count"] == 3

    def test_single_app_has_application_id(self, sample_applications):
        result = build_cluster_map_data(sample_applications)
        singles = result[result["cluster_count"] == 1]
        for _, row in singles.iterrows():
            assert row["application_id"] is not None

    def test_multi_app_cluster_has_no_application_id(
        self, sample_applications,
    ):
        result = build_cluster_map_data(sample_applications)
        clusters = result[result["cluster_count"] > 1]
        for _, row in clusters.iterrows():
            assert row["application_id"] is None

    def test_cluster_tooltip_shows_count(self, sample_applications):
        result = build_cluster_map_data(sample_applications)
        e3_cluster = result[result["postcode"] == "E3 4TN"]
        tooltip = e3_cluster.iloc[0]["tooltip_text"]
        assert "3 applications" in tooltip
        assert "Click to view all" in tooltip

    def test_single_tooltip_shows_application_number(
        self, sample_applications,
    ):
        result = build_cluster_map_data(sample_applications)
        e1_row = result[result["postcode"] == "E1 6QE"]
        tooltip = e1_row.iloc[0]["tooltip_text"]
        assert "PA/26/00089/FUL" in tooltip

    def test_empty_dataframe_returns_empty(self):
        empty_df = pd.DataFrame()
        result = build_cluster_map_data(empty_df)
        assert result.empty

    def test_result_has_required_columns(self, sample_applications):
        result = build_cluster_map_data(sample_applications)
        expected_columns = {
            "postcode", "lat", "long", "cluster_count",
            "color", "tooltip_text", "application_id",
        }
        assert expected_columns.issubset(set(result.columns))

    def test_cluster_uses_mean_coordinates(self, sample_applications):
        result = build_cluster_map_data(sample_applications)
        e3_cluster = result[result["postcode"] == "E3 4TN"]
        e3_apps = sample_applications[
            sample_applications["postcode"] == "E3 4TN"
        ]
        assert e3_cluster.iloc[0]["lat"] == pytest.approx(
            e3_apps["lat"].mean(),
        )
        assert e3_cluster.iloc[0]["long"] == pytest.approx(
            e3_apps["long"].mean(),
        )
