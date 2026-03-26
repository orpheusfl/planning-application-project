"""Tests for utils.components — Streamlit UI helpers and formatting."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from utils.components import (
    _score_pill,
    _status_badge,
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

    @pytest.mark.parametrize("score", [1, 2, 3, 4, 5])
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

    @pytest.mark.parametrize("score", [1, 2, 3, 4, 5])
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
    """Tests for components.get_selected_from_map."""

    @patch("utils.components.st")
    def test_valid_event_returns_selected_row(self, mock_st, sample_applications):
        mock_st.session_state = {}
        event = MagicMock()
        event.selection = {"indices": {"applications": [0]}}

        result = get_selected_from_map(event, sample_applications)

        assert result is not None
        assert result["application_id"] == sample_applications.iloc[0]["application_id"]

    @patch("utils.components.st")
    def test_empty_event_with_persisted_id_falls_back(self, mock_st, sample_applications):
        mock_st.session_state = {
            "map_selected_app_id": "th-2026-002",
        }
        event = MagicMock()
        event.selection = {}

        result = get_selected_from_map(event, sample_applications)

        assert result is not None
        assert result["application_id"] == "th-2026-002"

    @patch("utils.components.st")
    def test_none_event_with_no_persisted_returns_none(self, mock_st, sample_applications):
        mock_st.session_state = {}

        result = get_selected_from_map(None, sample_applications)

        assert result is None

    @patch("utils.components.st")
    def test_filters_changed_ignores_stale_event(self, mock_st, sample_applications):
        mock_st.session_state = {"_filters_changed": True}
        event = MagicMock()
        event.selection = {"indices": {"applications": [0]}}

        result = get_selected_from_map(event, sample_applications)

        # Should ignore the event because filters changed
        assert result is None

    @patch("utils.components.st")
    def test_persisted_id_not_in_filtered_set_clears_state(self, mock_st, sample_applications):
        session = {"map_selected_app_id": "th-NONEXISTENT"}
        mock_st.session_state = session

        result = get_selected_from_map(None, sample_applications)

        assert result is None
        assert "map_selected_app_id" not in session

    @patch("utils.components.st")
    def test_out_of_bounds_index_ignored(self, mock_st, sample_applications):
        mock_st.session_state = {}
        event = MagicMock()
        event.selection = {"indices": {"applications": [999]}}

        result = get_selected_from_map(event, sample_applications)

        assert result is None
