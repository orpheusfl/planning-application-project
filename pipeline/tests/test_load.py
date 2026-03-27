"""Tests for pipeline load module.

Tests cover all database interaction functions using a mock psycopg2
connection and cursor. Only the database layer is mocked — all
business logic (validation, error handling, branching) runs for real.
"""

from unittest.mock import patch

import pytest

from ..utilities.load import (
    get_council_id,
    get_status_type_id,
    get_application_type_id,
    insert_application_type,
    load_application_to_rds,
    validate_environment_variables,
    load_application_data,
)


# ============================================================================
# get_council_id
# ============================================================================


class TestGetCouncilId:
    """Tests for retrieving a council_id by name."""

    def test_returns_id_when_council_exists(self, mock_conn, mock_cursor):
        """Return the council_id when the council name is found."""
        mock_cursor.fetchone.return_value = (7,)

        result = get_council_id(mock_conn, "Tower Hamlets", "council")

        assert result == 7
        mock_cursor.execute.assert_called_once()

    def test_raises_value_error_when_council_not_found(
        self, mock_conn, mock_cursor
    ):
        """Raise ValueError when no matching council name exists."""
        mock_cursor.fetchone.return_value = None

        with pytest.raises(ValueError, match="Tower Hamlets"):
            get_council_id(mock_conn, "Tower Hamlets", "council")

    def test_raises_on_database_error(self, mock_conn, mock_cursor):
        """Propagate database errors from the cursor."""
        mock_cursor.execute.side_effect = Exception("connection lost")

        with pytest.raises(Exception, match="connection lost"):
            get_council_id(mock_conn, "Tower Hamlets", "council")


# ============================================================================
# get_status_type_id
# ============================================================================


class TestGetStatusTypeId:
    """Tests for retrieving a status_type_id by name."""

    def test_returns_id_when_status_exists(self, mock_conn, mock_cursor):
        """Return the status_type_id when the status name is found."""
        mock_cursor.fetchone.return_value = (3,)

        result = get_status_type_id(
            mock_conn, "Pending Decision", "status_type"
        )

        assert result == 3

    def test_raises_value_error_when_status_not_found(
        self, mock_conn, mock_cursor
    ):
        """Raise ValueError when no matching status name exists."""
        mock_cursor.fetchone.return_value = None

        with pytest.raises(ValueError, match="Pending Decision"):
            get_status_type_id(
                mock_conn, "Pending Decision", "status_type"
            )

    def test_raises_on_database_error(self, mock_conn, mock_cursor):
        """Propagate database errors from the cursor."""
        mock_cursor.execute.side_effect = Exception("timeout")

        with pytest.raises(Exception, match="timeout"):
            get_status_type_id(
                mock_conn, "Pending Decision", "status_type"
            )


# ============================================================================
# insert_application_type
# ============================================================================


class TestInsertApplicationType:
    """Tests for inserting a new application type."""

    def test_inserts_and_returns_new_id(self, mock_conn, mock_cursor):
        """Insert a new application type and return the generated id."""
        mock_cursor.fetchone.return_value = (42,)

        result = insert_application_type(
            mock_conn, "Advertising", "application_type"
        )

        assert result == 42
        mock_conn.commit.assert_called_once()

    def test_rolls_back_on_error(self, mock_conn, mock_cursor):
        """Roll back the transaction when the insert fails."""
        mock_cursor.execute.side_effect = Exception("duplicate key")

        with pytest.raises(Exception, match="duplicate key"):
            insert_application_type(
                mock_conn, "Advertising", "application_type"
            )

        mock_conn.rollback.assert_called_once()


# ============================================================================
# get_application_type_id
# ============================================================================


class TestGetApplicationTypeId:
    """Tests for retrieving or creating an application_type_id."""

    def test_returns_id_when_type_exists(self, mock_conn, mock_cursor):
        """Return the id when the application type already exists."""
        mock_cursor.fetchone.return_value = (5,)

        result = get_application_type_id(
            mock_conn, "Full Planning", "application_type"
        )

        assert result == 5

    def test_inserts_when_type_not_found(self, mock_conn, mock_cursor):
        """Insert the type and return a new id when not found."""
        # First call (SELECT) returns None, second call (INSERT) returns id
        mock_cursor.fetchone.side_effect = [None, (99,)]

        result = get_application_type_id(
            mock_conn, "New Type", "application_type"
        )

        assert result == 99
        assert mock_cursor.execute.call_count == 2

    def test_rolls_back_on_error(self, mock_conn, mock_cursor):
        """Roll back on database error during lookup."""
        mock_cursor.execute.side_effect = Exception("connection reset")

        with pytest.raises(Exception, match="connection reset"):
            get_application_type_id(
                mock_conn, "Full Planning", "application_type"
            )

        mock_conn.rollback.assert_called_once()


# ============================================================================
# load_application_to_rds
# ============================================================================


class TestLoadApplicationToRds:
    """Tests for inserting a full application record."""

    def test_inserts_and_returns_application_id(
        self, mock_conn, mock_cursor, sample_application_info
    ):
        """Insert the application and return the generated id."""
        mock_cursor.fetchone.return_value = (101,)

        result = load_application_to_rds(
            mock_conn, "application", sample_application_info,
            council_id=1, status_type_id=2, application_type_id=3,
        )

        assert result == 101
        mock_conn.commit.assert_called_once()
        mock_cursor.execute.assert_called_once()

    def test_passes_all_fields_to_query(
        self, mock_conn, mock_cursor, sample_application_info
    ):
        """Verify all application fields are passed to the INSERT."""
        mock_cursor.fetchone.return_value = (1,)

        load_application_to_rds(
            mock_conn, "application", sample_application_info,
            council_id=1, status_type_id=2, application_type_id=3,
        )

        args = mock_cursor.execute.call_args[0][1]
        assert args[0] == "PA/26/00142/A1"
        assert args[3] == "E3 4TN"
        assert args[7] == 8
        assert args[8] == 1   # council_id
        assert args[9] == 2   # status_type_id
        assert args[10] == 3  # application_type_id

    def test_rolls_back_on_error(
        self, mock_conn, mock_cursor, sample_application_info
    ):
        """Roll back the transaction when the insert fails."""
        mock_cursor.execute.side_effect = Exception("constraint violation")

        with pytest.raises(Exception, match="constraint violation"):
            load_application_to_rds(
                mock_conn, "application", sample_application_info,
                council_id=1, status_type_id=2, application_type_id=3,
            )

        mock_conn.rollback.assert_called_once()


# ============================================================================
# validate_environment_variables
# ============================================================================


class TestValidateEnvironmentVariables:
    """Tests for environment variable validation."""

    @patch.dict(
        "os.environ",
        {
            "APPLICATION_FACT_TABLE": "application",
            "COUNCIL_DIM_TABLE": "council",
            "STATUS_DIM_TABLE": "status_type",
            "APPLICATION_TYPE_DIM_TABLE": "application_type",
        },
    )
    def test_passes_when_all_vars_set(self):
        """No error when all required environment variables are present."""
        validate_environment_variables()

    @patch.dict("os.environ", {}, clear=True)
    def test_raises_when_all_vars_missing(self):
        """Raise ValueError when all required variables are absent."""
        with pytest.raises(
            ValueError, match="Missing required environment variables"
        ):
            validate_environment_variables()

    @patch.dict(
        "os.environ",
        {
            "APPLICATION_FACT_TABLE": "application",
            "COUNCIL_DIM_TABLE": "council",
        },
        clear=True,
    )
    def test_raises_listing_only_missing_vars(self):
        """Raise ValueError naming only the missing variable names."""
        with pytest.raises(ValueError, match="STATUS_DIM_TABLE"):
            validate_environment_variables()


# ============================================================================
# load_application_data (orchestration)
# ============================================================================


class TestLoadApplicationData:
    """Tests for the top-level orchestration function."""

    @patch.dict(
        "os.environ",
        {
            "APPLICATION_FACT_TABLE": "application",
            "COUNCIL_DIM_TABLE": "council",
            "STATUS_DIM_TABLE": "status_type",
            "APPLICATION_TYPE_DIM_TABLE": "application_type",
        },
    )
    def test_orchestrates_full_load(
        self, mock_conn, mock_cursor, sample_application_info
    ):
        """Call all helper functions in sequence to load an application."""
        # Council lookup, status lookup, app type lookup, insert
        mock_cursor.fetchone.side_effect = [(1,), (2,), (3,), (101,)]

        load_application_data(
            mock_conn, "Tower Hamlets", sample_application_info
        )

        assert mock_cursor.execute.call_count == 4

    @patch.dict("os.environ", {}, clear=True)
    def test_raises_when_env_vars_missing(
        self, mock_conn, sample_application_info
    ):
        """Fail early when environment variables are not configured."""
        with pytest.raises(ValueError, match="Missing required"):
            load_application_data(
                mock_conn, "Tower Hamlets", sample_application_info
            )

    @patch.dict(
        "os.environ",
        {
            "APPLICATION_FACT_TABLE": "application",
            "COUNCIL_DIM_TABLE": "council",
            "STATUS_DIM_TABLE": "status_type",
            "APPLICATION_TYPE_DIM_TABLE": "application_type",
        },
    )
    def test_raises_when_council_not_found(
        self, mock_conn, mock_cursor, sample_application_info
    ):
        """Propagate ValueError when the council name is invalid."""
        mock_cursor.fetchone.return_value = None

        with pytest.raises(ValueError, match="Tower Hamlets"):
            load_application_data(
                mock_conn, "Tower Hamlets", sample_application_info
            )
