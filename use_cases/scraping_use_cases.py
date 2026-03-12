import logging
from adapters.repositories.sqlite_repo import SQLiteRepository
from adapters.scrapers.duckduckgo_bot import DuckDuckGoScraperAdapter

logger = logging.getLogger(__name__)

class ScrapingUseCases:
    def __init__(self, repo: SQLiteRepository):
        self.repo = repo
        
    def execute_job_hunt(self, user_id: int, limit: int = 200, use_proxy: bool = True):
        # 1. Fetch domain configurations via Repo
        from use_cases.auth_use_cases import SettingsUseCases
        roles = self.repo.get_target_roles(user_id, active_only=True)
        role_names = [r.role_name for r in roles]
        
        if not role_names:
            logger.warning(f"User {user_id} has no active roles. Skipping hunt.")
            return 0
            
        settings_uc = SettingsUseCases(self.repo)
        countries = settings_uc.get_countries(user_id)
        
        jobs_inserted = 0
        
        for country in countries:
            if country.lower() in ('brasil', 'brazil'):
                region = 'br-pt'
            elif country.lower() in ('portugal', 'pt'):
                region = 'pt-pt'
            else:
                region = 'us-en'
                
            # 2. Instantiate External Adapter (Scraper) per Country
            scraper = DuckDuckGoScraperAdapter(use_proxy=use_proxy, country=country, region=region)
            
            # 3. Instruct Adapter to fetch raw logic
            logger.info(f"Firing up scraper for User {user_id} on roles {role_names} in {country}")
            raw_jobs = scraper.scrape_roles(role_names, limit=limit)
            
            # 4. Save results back through Repo
            for job_data in raw_jobs:
                success = self.repo.insert_job(user_id, job_data)
                if success:
                    jobs_inserted += 1
                    
        # 5. Formally log the execution run across all countries
        self.repo.log_run(user_id, role_names, jobs_inserted)
        logger.info(f"Run completed for User {user_id}. {jobs_inserted} unique jobs inserted across {len(countries)} countries.")
        
        return jobs_inserted
