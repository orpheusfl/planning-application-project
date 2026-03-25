from extract_helpers4 import run_scraper

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from extract_helpers4 import run_scraper, BASE_URL


def _modify_app_url(url: str, target_tab: str) -> str:
    """
    Internal helper to swap the activeTab parameter in an Idox URL.
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    # Update the tab while keeping the unique keyVal
    params['activeTab'] = [target_tab]

    # Rebuild the query string
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def get_summary_url_for_application(app_data: dict) -> str:
    """
    Ensures the URL is pointing to the summary tab.
    """
    return _modify_app_url(app_data['url'], 'summary')


def get_documents_url_for_application(app_data: dict) -> str:
    """
    Generates the Documents tab URL from the base application URL.
    """
    return _modify_app_url(app_data['url'], 'documents')


def get_further_details_url_for_application(app_data: dict) -> str:
    """
    Generates the Further Details tab URL from the base application URL.
    """
    return _modify_app_url(app_data['url'], 'details')


if __name__ == "__main__":
    # 1. Get the data using your existing logic
    apps = run_scraper()

    if apps:
        first_app = apps[0]

        # 2. Generate the specific links
        summary = get_summary_url_for_application(first_app)
        docs = get_documents_url_for_application(first_app)

        print(f"ID: {first_app['application_id']}")
        print(f"Summary Link: {summary}")
        print(f"Docs Link:    {docs}")
