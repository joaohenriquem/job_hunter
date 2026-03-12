import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
import re
import random
from adapters.scrapers.proxy_utils import get_free_proxies

logger = logging.getLogger(__name__)

class DuckDuckGoScraperAdapter:
    """
    Adapter decoupled from database and application logic.
    Returns dictionaries of jobs instead of saving them itself.
    """
    def __init__(self, use_proxy=True, country='Brasil', region='br-pt'):
        self.use_proxy = use_proxy
        self.country = country
        self.region = region
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        if self.use_proxy:
            logger.info("Fetching free proxies...")
            self.proxies = get_free_proxies()
        else:
            self.proxies = []

    def _get_proxy(self):
        if not self.proxies:
            return None
        return random.choice(self.proxies)

    def scrape_roles(self, roles, limit=500):
        all_jobs_found = []
        for role in roles:
            jobs = self._search_single_role(role, limit)
            all_jobs_found.extend(jobs)
        return all_jobs_found

    def _search_single_role(self, role, limit=500):
        target_sites = []
        if self.country.lower() in ('brasil', 'brazil'):
            target_sites = ['gupy.io', 'linkedin.com/jobs', 'vagas.com.br', 'catho.com.br']
        else:
            target_sites = ['linkedin.com/jobs', 'indeed.com/viewjob', 'glassdoor.com/job-listing']
        
        all_results = []
        max_retries = 3

        for site in target_sites:
            # Aspas ao redor do cargo garantem busca exata da expressao
            query = f'"{role}" site:{site}'
            if self.country.lower() not in ('brasil', 'brazil'):
                query += f' {self.country}'
                
            site_results = []

            if self.use_proxy:
                for i in range(max_retries):
                    current_proxy = self._get_proxy()
                    try:
                        with DDGS(proxy=current_proxy, timeout=20) as ddgs:
                            site_limit = max(10, limit // len(target_sites))
                            site_results = list(ddgs.text(query, region=self.region, safesearch='off', max_results=site_limit))
                        break
                    except Exception:
                        pass
            
            if not site_results:
                try:
                    with DDGS(timeout=20) as ddgs:
                        site_limit = max(10, limit // len(target_sites))
                        site_results = list(ddgs.text(query, region=self.region, safesearch='off', max_results=site_limit))
                except Exception as e:
                    logger.error(f"  Direct connection failed for {site}: {e}")
                    
            if site_results:
                all_results.extend(site_results)
        
        urls_to_scrape = []
        for r in all_results:
            raw_url = r.get('href', '')
            url = raw_url.split('?')[0].split('#')[0] if raw_url else ''
            title = r.get('title', 'No Title')
            
            url_lower = url.lower()
            title_lower = title.lower()
            
            # Aceita qualquer subdominio do Gupy (empresa.gupy.io/jobs/ ou empresa.gupy.io/job/)
            is_gupy = ('gupy.io/jobs/' in url_lower or 'gupy.io/job/' in url_lower)
            valid_job_paths = [
                'vagas.com.br/vagas/', 'catho.com.br/vagas/',
                'linkedin.com/jobs/view/',
                'indeed.com/viewjob', 'glassdoor.com/job-listing/'
            ]
            is_valid_url = is_gupy or any(path in url_lower for path in valid_job_paths)
            
            # Remove apenas resultados claramente irrelevantes (cursos, blogs sobre vagas)
            has_bad_pattern = 'vagaa' in title_lower or any('\u4e00' <= c <= '\u9fff' for c in title) or 'curso' in title_lower
            
            if not url or not is_valid_url or has_bad_pattern:
                continue

            urls_to_scrape.append((url, title, role))

        scraped_jobs = []
        max_workers = min(10, len(urls_to_scrape) if urls_to_scrape else 1)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(self._extract_details, url_info): url_info for url_info in urls_to_scrape}
            
            for future in as_completed(future_to_url):
                url, title, role = future_to_url[future]
                try:
                    email, apply_link, is_home_office, company, description = future.result()
                    scraped_jobs.append({
                        'Role': role,
                        'Title': title,
                        'URL': url,
                        'Email': email,
                        'Company': company,
                        'Description': description,
                        'Home Office': 'Yes' if is_home_office else 'No',
                        'Apply Link': apply_link
                    })
                except Exception as e:
                    logger.error(f"Error extracting {url}: {e}")
                    
        return scraped_jobs

    def _extract_details(self, url_info):
        url, title, role = url_info
        
        for i in range(2):
            proxies = None
            if self.use_proxy:
                current_proxy = self._get_proxy()
                proxies = {"http": current_proxy, "https": current_proxy} if current_proxy else None
            
            try:
                resp = requests.get(url, headers=self.headers, proxies=proxies, timeout=10)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    text = soup.get_text()
                    
                    emails = set()
                    for a in soup.select('a[href^="mailto:"]'):
                        email = a['href'].replace('mailto:', '').split('?')[0].strip()
                        if email: emails.add(email)
                    
                    regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                    found = re.findall(regex, text)
                    for f in found:
                        if not f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.css', '.js')):
                            emails.add(f)
                    email_str = ", ".join(emails) if emails else None
                    
                    company = None
                    company_meta = soup.find('meta', property='og:site_name') or soup.find('meta', attrs={'name': 'author'})
                    if company_meta and company_meta.get('content'):
                        company = company_meta.get('content').strip()
                    
                    if not company:
                        company_selectors = [
                            soup.find(class_=re.compile(r'company|employer', re.I)),
                        ]
                        for selector in company_selectors:
                            if selector and selector.get_text(strip=True):
                                company = selector.get_text(strip=True)[:50]
                                break
                    
                    description = None
                    desc_selectors = [
                        soup.find('div', class_=re.compile(r'description|job-description|jobdescription', re.I)),
                        soup.find('section', class_=re.compile(r'description|job-description', re.I))
                    ]
                    for selector in desc_selectors:
                        if selector:
                            desc_text = selector.get_text(separator=' ', strip=True)
                            if len(desc_text) > 50:
                                description = desc_text[:1000]
                                break
                    
                    is_home_office = any(keyword in text.lower() for keyword in ['home office', 'remoto', 'remote', 'trabalho em casa'])
                    return email_str, url, is_home_office, company, description
            except requests.RequestException:
                pass
            except Exception:
                pass
        
        return None, url, False, None, None
