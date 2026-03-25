"""Tests for utils.subscribers — database operations for subscriptions."""

from unittest.mock import call

import pytest

from utils.subscribers import (
    deactivate_all_subscriptions,
    deactivate_subscriptions,
    get_active_subscriptions,
    insert_subscriber,
)


class TestGetActiveSubscriptions:
    """Tests for subscribers.get_active_subscriptions."""

    def test_returns_list_of_dicts_when_rows_exist(self, mock_db_connection):
        conn, cursor = mock_db_connection
        cursor.description = [
            ("subscriber_id",),
            ("postcode",),
            ("radius_miles",),
            ("min_interest_score",),
        ]
        cursor.fetchall.return_value = [
            (1, "E1 4TT", 0.5, 3),
            (2, "E2 0HU", 1.0, 1),
        ]

        result = get_active_subscriptions(conn, "test@example.com")

        assert len(result) == 2
        assert result[0] == {
            "subscriber_id": 1,
            "postcode": "E1 4TT",
            "radius_miles": 0.5,
            "min_interest_score": 3,
        }
        assert result[1]["postcode"] == "E2 0HU"

    def test_returns_empty_list_for_unknown_email(self, mock_db_connection):
        conn, cursor = mock_db_connection
        cursor.description = [
            ("subscriber_id",),
            ("postcode",),
            ("radius_miles",),
            ("min_interest_score",),
        ]
        cursor.fetchall.return_value = []

        result = get_active_subscriptions(conn, "nobody@example.com")
        assert result == []

    def test_passes_email_as_parameter(self, mock_db_connection):
        conn, cursor = mock_db_connection
        cursor.description = [
            ("subscriber_id",),
            ("postcode",),
            ("radius_miles",),
            ("min_interest_score",),
        ]
        cursor.fetchall.return_value = []

        get_active_subscriptions(conn, "user@test.com")

        args = cursor.execute.call_args
        assert args[0][1] == ("user@test.com",)


class TestDeactivateAllSubscriptions:
    """Tests for subscribers.deactivate_all_subscriptions."""

    def test_executes_update_query(self, mock_db_connection):
        conn, cursor = mock_db_connection

        deactivate_all_subscriptions(conn, "test@example.com")

        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]
        assert "UPDATE" in sql.upper()
        assert "subscribers" in sql

    def test_passes_email_parameter(self, mock_db_connection):
        conn, cursor = mock_db_connection

        deactivate_all_subscriptions(conn, "test@example.com")

        args = cursor.execute.call_args[0][1]
        assert args == ("test@example.com",)

    def test_commits_after_update(self, mock_db_connection):
        conn, cursor = mock_db_connection

        deactivate_all_subscriptions(conn, "test@example.com")

        conn.commit.assert_called_once()


class TestInsertSubscriber:
    """Tests for subscribers.insert_subscriber."""

    def test_executes_insert_query(self, mock_db_connection):
        conn, cursor = mock_db_connection

        insert_subscriber(
            conn, "a@b.com", "E1 4TT", 51.51, -0.09, 0.5, 3
        )

        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]
        assert "INSERT" in sql.upper()
        assert "subscribers" in sql

    def test_passes_all_parameters(self, mock_db_connection):
        conn, cursor = mock_db_connection

        insert_subscriber(
            conn, "a@b.com", "E1 4TT", 51.51, -0.09, 0.5, 3
        )

        params = cursor.execute.call_args[0][1]
        assert params == ("a@b.com", "E1 4TT", 51.51, -0.09, 0.5, 3)

    def test_commits_after_insert(self, mock_db_connection):
        conn, cursor = mock_db_connection

        insert_subscriber(
            conn, "a@b.com", "E1 4TT", 51.51, -0.09, 0.5, 3
        )

        conn.commit.assert_called_once()

    def test_different_parameters_are_forwarded(self, mock_db_connection):
        conn, cursor = mock_db_connection

        insert_subscriber(
            conn, "other@mail.com", "E2 0HU", 51.53, -0.05, 2.0, 5
        )

        params = cursor.execute.call_args[0][1]
        assert params == ("other@mail.com", "E2 0HU", 51.53, -0.05, 2.0, 5)


class TestDeactivateSubscriptions:
    """Tests for subscribers.deactivate_subscriptions."""

    def test_executes_update_with_ids(self, mock_db_connection):
        conn, cursor = mock_db_connection

        deactivate_subscriptions(conn, [1, 2, 3])

        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]
        assert "UPDATE" in sql.upper()
        assert "subscribers" in sql

    def test_passes_subscriber_ids_as_parameter(self, mock_db_connection):
        conn, cursor = mock_db_connection

        deactivate_subscriptions(conn, [10, 20])

        params = cursor.execute.call_args[0][1]
        assert params == ([10, 20],)

    def test_commits_after_update(self, mock_db_connection):
        conn, cursor = mock_db_connection

        deactivate_subscriptions(conn, [1])

        conn.commit.assert_called_once()

    def test_empty_list_skips_query(self, mock_db_connection):
        conn, cursor = mock_db_connection

        deactivate_subscriptions(conn, [])

        cursor.execute.assert_not_called()
        conn.commit.assert_not_called()

    def test_single_id(self, mock_db_connection):
        conn, cursor = mock_db_connection

        deactivate_subscriptions(conn, [42])

        params = cursor.execute.call_args[0][1]
        assert params == ([42],)
