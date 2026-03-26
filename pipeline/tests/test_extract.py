"""
Unit tests for the extract module.

Tests focus on parsing logic and URL manipulation functions that don't require
heavy mocking or network calls.
"""

import pytest
from bs4 import BeautifulSoup
from ..utilities.extract import (
    clean_html_text,
    _modify_app_url,
    get_tab_url,
    extract_application_id,
    extract_application_url,
    parse_search_result,
)


# --- Tests for clean_html_text ---


def test_clean_html_text_with_valid_element():
    """Test cleaning text from a valid HTML element."""
    html = "<p>  Hello   World  </p>"
    soup = BeautifulSoup(html, "html.parser")
    element = soup.find("p")

    result = clean_html_text(element)

    assert result == "Hello World"


def test_clean_html_text_with_none():
    """Test that None returns 'N/A'."""
    result = clean_html_text(None)
    assert result == "N/A"


def test_clean_html_text_with_newlines_and_nbsp():
    """Test cleaning text with multiple newlines and non-breaking spaces."""
    html = "<p>Line1\n\n  Line2&nbsp;&nbsp;Line3</p>"
    soup = BeautifulSoup(html, "html.parser")
    element = soup.find("p")

    result = clean_html_text(element)

    assert result == "Line1 Line2 Line3"


def test_clean_html_text_with_empty_element():
    """Test cleaning an empty HTML element."""
    html = "<p>   </p>"
    soup = BeautifulSoup(html, "html.parser")
    element = soup.find("p")

    result = clean_html_text(element)

    assert result == ""


# --- Tests for _modify_app_url ---


def test_modify_app_url_replaces_activetab():
    """Test that _modify_app_url correctly replaces the activeTab parameter."""
    url = "https://example.com/app?id=123&activeTab=summary"
    result = _modify_app_url(url, "documents")

    assert "activeTab=documents" in result
    assert "id=123" in result


def test_modify_app_url_adds_activetab_if_missing():
    """Test that _modify_app_url adds activeTab if not present."""
    url = "https://example.com/app?id=123"
    result = _modify_app_url(url, "summary")

    assert "activeTab=summary" in result
    assert "id=123" in result


def test_modify_app_url_preserves_other_params():
    """Test that other query parameters are preserved when modifying activeTab."""
    url = "https://example.com/app?status=active&activeTab=summary&page=1"
    result = _modify_app_url(url, "details")

    assert "activeTab=details" in result
    assert "status=active" in result
    assert "page=1" in result


# --- Tests for get_tab_url ---


def test_get_tab_url_returns_correct_tab_url():
    """Test that get_tab_url generates the correct URL for a given tab."""
    app_data = {"url": "https://example.com/app?id=PA/01/001&activeTab=summary"}
    result = get_tab_url(app_data, "documents")

    assert "activeTab=documents" in result
    assert "PA%2F01%2F001" in result


# --- Tests for extract_application_id ---


def test_extract_application_id_with_valid_meta_tag():
    """Test extracting application ID from a valid search result element."""
    html = """
    <li class="searchresult">
        <p class="metaInfo">Ref. No: PA/22/01234 | Validated: 01/01/2022</p>
    </li>
    """
    soup = BeautifulSoup(html, "html.parser")
    app_html = soup.find("li", class_="searchresult")

    result = extract_application_id(app_html)

    assert result == "PA/22/01234"


def test_extract_application_id_with_extra_whitespace():
    """Test extracting application ID with extra whitespace."""
    html = """
    <li class="searchresult">
        <p class="metaInfo">  Ref. No:   PA/99/99999  |  Validated: 01/01/2022  </p>
    </li>
    """
    soup = BeautifulSoup(html, "html.parser")
    app_html = soup.find("li", class_="searchresult")

    result = extract_application_id(app_html)

    assert result == "PA/99/99999"


def test_extract_application_id_without_meta_tag():
    """Test that 'N/A' is returned when metaInfo tag is missing."""
    html = "<li class='searchresult'><p>No meta info</p></li>"
    soup = BeautifulSoup(html, "html.parser")
    app_html = soup.find("li", class_="searchresult")

    result = extract_application_id(app_html)

    assert result == "N/A"


def test_extract_application_id_without_ref_no():
    """Test that 'N/A' is returned when Ref. No is missing."""
    html = """
    <li class="searchresult">
        <p class="metaInfo">Validated: 01/01/2022</p>
    </li>
    """
    soup = BeautifulSoup(html, "html.parser")
    app_html = soup.find("li", class_="searchresult")

    result = extract_application_id(app_html)

    assert result == "N/A"


# --- Tests for extract_application_url ---


def test_extract_application_url_with_valid_link():
    """Test extracting application URL from a search result element."""
    html = """
    <li class="searchresult">
        <a href="view-application.do?id=PA/22/01234">View Application</a>
    </li>
    """
    soup = BeautifulSoup(html, "html.parser")
    app_html = soup.find("li", class_="searchresult")

    result = extract_application_url(app_html)

    assert "https://development.towerhamlets.gov.uk/online-applications/" in result
    assert "PA/22/01234" in result


def test_extract_application_url_without_link():
    """Test that 'N/A' is returned when no link is present."""
    html = "<li class='searchresult'><p>No link</p></li>"
    soup = BeautifulSoup(html, "html.parser")
    app_html = soup.find("li", class_="searchresult")

    result = extract_application_url(app_html)

    assert result == "N/A"


def test_extract_application_url_without_href():
    """Test that 'N/A' is returned when link has no href."""
    html = "<li class='searchresult'><a>No href</a></li>"
    soup = BeautifulSoup(html, "html.parser")
    app_html = soup.find("li", class_="searchresult")

    result = extract_application_url(app_html)

    assert result == "N/A"


# --- Tests for parse_search_result ---


def test_parse_search_result_with_complete_data():
    """Test parsing a complete search result element."""
    html = """
    <li class="searchresult">
        <p class="metaInfo">Ref. No: PA/22/01234 | Validated: 01/01/2022</p>
        <a href="view-application.do?id=PA/22/01234">View Application</a>
    </li>
    """
    soup = BeautifulSoup(html, "html.parser")
    app_html = soup.find("li", class_="searchresult")

    result = parse_search_result(app_html)

    assert result["application_id"] == "PA/22/01234"
    assert "https://development.towerhamlets.gov.uk/online-applications/" in result["url"]
    assert "PA/22/01234" in result["url"]


def test_parse_search_result_with_missing_data():
    """Test parsing a search result with missing application ID and URL."""
    html = "<li class='searchresult'><p>Incomplete data</p></li>"
    soup = BeautifulSoup(html, "html.parser")
    app_html = soup.find("li", class_="searchresult")

    result = parse_search_result(app_html)

    assert result["application_id"] == "N/A"
    assert result["url"] == "N/A"
