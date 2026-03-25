import requests
import urllib3

# Suppress the warning that appears when you bypass SSL verification
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_fresh_session():
    session = requests.Session()
    cookie_trigger_url = "https://development.towerhamlets.gov.uk/online-applications/"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive"
    }

    print(f"Fetching fresh session from: {cookie_trigger_url}")

    # ADDED: verify=False to bypass the strict SSL check
    response = session.get(cookie_trigger_url, headers=headers, verify=False)

    if 'JSESSIONID' in session.cookies:
        print(f"Success! Captured JSESSIONID: {session.cookies['JSESSIONID']}")
    else:
        print("Warning: Did not capture a JSESSIONID. Check the status code or headers.")

    # Note: You will also need to add verify=False to any future requests you make with this scraper!
    # session.verify = False # You can actually set it on the session level so you don't have to type it every time.

    return session


if __name__ == "__main__":
    # The session will now be configured to ignore SSL errors
    scraper = get_fresh_session()

    # Pro-tip: tell the entire session to ignore SSL so you don't have to
    # add verify=False to every single scraper.get() call later.
    scraper.verify = False
