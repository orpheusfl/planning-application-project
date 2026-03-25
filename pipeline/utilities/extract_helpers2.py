import requests
from bs4 import BeautifulSoup
import urllib3

# 1. Setup
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Replace these with your current active session details from the Network tab
ACTIVE_COOKIE = "JSESSIONID=4IYufvrBPDgQiCV1jBaGNZqHyzckf7MawenXtUzb.tow-azs-p-paw01; _gcl_au=1.1.219897284.1774371480; _ga_CM7HE0C0K6=GS2.1.s1774429253$o3$g1$t1774429255$j58$l0$h0; _ga=GA1.3.643158694.1774371480; _fbp=fb.2.1774371480582.232791374789910922; __qca=P1-7e7911aa-ef45-440f-afbb-28d877049682; _gid=GA1.3.1959656001.1774371487; _ga_DZWFGT4PEW=GS2.3.s1774429259$o2$g1$t1774429290$j29$l0$h0; _uetsid=9daac2a027a211f1adabb5acc7798655; _uetvid=9daad9a027a211f183db5be6d7ff1557; _gat=1"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) Gecko/20100101 Firefox/148.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://development.towerhamlets.gov.uk/online-applications/currentListResults.do?action=firstPage',
    'Cookie': ACTIVE_COOKIE,
    'Connection': 'keep-alive'
}

BASE_URL = "https://development.towerhamlets.gov.uk/online-applications/"


def scrape_pages(total_pages=3):
    all_data = []

    for page in range(1, total_pages + 1):
        print(f"--- Fetching Page {page} ---")
        url = f"{BASE_URL}pagedSearchResults.do?action=page&searchCriteria.page={page}"

        response = requests.get(url, headers=HEADERS, verify=False)

        if "session has timed out" in response.text:
            print(
                "❌ Error: Cookie expired! Refresh your browser and update ACTIVE_COOKIE.")
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        apps = soup.find_all('li', class_='searchresult')

        if not apps:
            print(f"No applications found on page {page}. Stopping.")
            break

        for app in apps:
            link_tag = app.find('a')
            ref = link_tag.text.strip()
            details_url = BASE_URL + link_tag['href']

            # The address is usually in the first <p> or a specific class
            address = "N/A"
            address_tag = app.find('p', class_='address')
            if address_tag:
                address = address_tag.text.strip()

            all_data.append({
                "ref": ref,
                "address": address,
                "url": details_url
            })
            print(f"Found: {ref}")

    return all_data


if __name__ == "__main__":
    # Adjust based on how many pages you want
    results = scrape_pages(total_pages=2)
    print(f"\n✅ Total applications found: {len(results)}")
