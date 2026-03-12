import argparse
import logging
import sys
import os

# Adiciona a raiz do projeto no sys.path para importações absolutas funcionarem
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from adapters.repositories.sqlite_repo import SQLiteRepository
from use_cases.scraping_use_cases import ScrapingUseCases

logging.basicConfig(level=logging.INFO, format='%(asctime)s - SCRAPER: %(message)s')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CLI Entrypoint para rodar o orquestrador Clean Architecture de Vagas")
    parser.add_argument('--user-id', type=int, required=True, 
                        help="ID do usuario dono da execucao")
    parser.add_argument('--limit', type=int, default=1000, 
                        help="Maximum number of search results per role")
    parser.add_argument('--no-proxy', action='store_true', 
                        help="Disable proxy rotation and use direct connection")
    
    args = parser.parse_args()
    
    # Injeta a implementação concreta do BD no Use Case puro
    repo = SQLiteRepository()
    use_case = ScrapingUseCases(repo)
    
    use_case.execute_job_hunt(
        user_id=args.user_id, 
        limit=args.limit, 
        use_proxy=not args.no_proxy
    )
