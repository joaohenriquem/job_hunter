import requests
from bs4 import BeautifulSoup
import random

def get_free_proxies():
    """
    Fetches free proxies from sslproxies.org.
    Returns a list of proxy strings in format 'http://ip:port'.
    """
    url = "https://www.sslproxies.org/"
    try:
        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        proxies = []
        
        # The table usually has id 'proxylisttable' or similar, but structure changes.
        # Often it is in a table class 'table table-striped table-bordered'
        # We'll look for trs in tbody
        
        # Depending on current site layout:
        # Columns: IP, Port, Code, Country, Anonymity, Google, Https, Last Checked
        
        table = soup.find('table')
        if not table:
            return []
            
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 2:
                ip = cols[0].text.strip()
                port = cols[1].text.strip()
                # Basic validation that it looks like IP
                if ip.count('.') == 3:
                    # Construct proxy string
                    # Note: These are usually HTTP/HTTPS proxies
                    proxies.append(f"http://{ip}:{port}")
        
        return proxies
    except Exception as e:
        print(f"Error fetching proxies: {e}")
        return []

if __name__ == "__main__":
    p = get_free_proxies()
    print(f"Found {len(p)} proxies.")
    print(p[:5])
