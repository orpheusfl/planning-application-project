import requests
from bs4 import BeautifulSoup
import urllib3

# Setup
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration object to avoid global variables where possible
CONFIG = {
    "base_url": "https://development.towerhamlets.gov.uk/online-applications/",
    "active_cookie": "JSESSIONID=4IYufvrBPDgQiCV1jBaGNZqHyzckf7MawenXtUzb.tow-azs-p-paw01; _gcl_au=1.1.219897284.1774371480; _ga_CM7HE0C0K6=GS2.1.s1774429253$o3$g1$t1774429255$j58$l0$h0; _ga=GA1.3.643158694.1774371480; _fbp=fb.2.1774371480582.232791374789910922; __qca=P1-7e7911aa-ef45-440f-afbb-28d877049682; _gid=GA1.3.1959656001.1774371487; _ga_DZWFGT4PEW=GS2.3.s1774429259$o2$g1$t1774429290$j29$l0$h0; _uetsid=9daac2a027a211f1adabb5acc7798655; _uetvid=9daad9a027a211f183db5be6d7ff1557; _gat=1",
    "headers": {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) Gecko/20100101 Firefox/148.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://development.towerhamlets.gov.uk/online-applications/currentListResults.do?action=firstPage',
        'Connection': 'keep-alive'
    }
}


def get_page_html(page_number):
    """Fetches the raw HTML for a specific results page."""
    url = f"{CONFIG['base_url']}pagedSearchResults.do?action=page&searchCriteria.page={page_number}"
    headers = {**CONFIG['headers'], 'Cookie': CONFIG['active_cookie']}

    response = requests.get(url, headers=headers, verify=False)

    if "session has timed out" in response.text:
        raise ConnectionRefusedError("Cookie expired. Update ACTIVE_COOKIE.")

    return response.text


def parse_application_item(app_tag):
    """Extracts data from a single <li> application element."""
    link_tag = app_tag.find('a')
    if not link_tag:
        return None

    address_tag = app_tag.find('p', class_='address')

    return {
        "ref": link_tag.text.strip(),
        "address": address_tag.text.strip() if address_tag else "N/A",
        "url": CONFIG['base_url'] + link_tag['href']
    }


def scrape_single_page(page_number):
    """Orchestrates fetching and parsing of one results page."""
    try:
        html = get_page_html(page_number)
        soup = BeautifulSoup(html, 'html.parser')
        app_tags = soup.find_all('li', class_='searchresult')

        # Use list comprehension for cleaner data gathering
        return [data for tag in app_tags if (data := parse_application_item(tag))]
    except ConnectionRefusedError as e:
        print(f"❌ {e}")
        return None


def run_scraper(limit):
    """Main loop to process multiple pages."""
    all_results = []

    for page in range(1, limit + 1):
        print(f"--- Processing Page {page} ---")
        page_data = scrape_single_page(page)

        if not page_data:  # Stop if timeout occurred or no more data
            break

        all_results.extend(page_data)
        print(f"Collected {len(page_data)} items from page {page}.")

    return all_results


if __name__ == "__main__":
    results = run_scraper(limit=8)
    print(f"\n✅ Scraping complete. Total: {len(results)} applications.")
