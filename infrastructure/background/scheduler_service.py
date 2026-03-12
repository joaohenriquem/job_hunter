import schedule
import time
import logging
import subprocess
import os
import sys

# Adiciona a raiz do projeto no sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from adapters.repositories.sqlite_repo import SQLiteRepository
from use_cases.auth_use_cases import AuthUseCases
from use_cases.auth_use_cases import SettingsUseCases

logging.basicConfig(level=logging.INFO, format='%(asctime)s - SCHEDULER: %(message)s')

SCRAPER_SCRIPT = os.path.join(os.path.dirname(__file__), 'run_scraper.py')

def run_job_hunter(user_id):
    logging.info(f"Triggering background scraper run for User ID {user_id}...")
    try:
        result = subprocess.run(['python', SCRAPER_SCRIPT, '--limit', '200', '--no-proxy', '--user-id', str(user_id)], 
                                capture_output=True, text=True)
        
        logging.info(f"Scraper finished for User {user_id} with exit code {result.returncode}")
        
        if result.returncode != 0:
            logging.error(f"Scraper errors (User {user_id}): {result.stderr}")
            
    except Exception as e:
        logging.error(f"Failed to run scraper subprocess: {e}")

if __name__ == "__main__":
    logging.info("Starting Job Hunter Multi-Tenant Scheduler (Clean Architecture)...")
    
    repo = SQLiteRepository()
    auth_uc = AuthUseCases(repo)
    settings_uc = SettingsUseCases(repo)
    
    user_frequencies = {}
    
    while True:
        try:
            users = auth_uc.get_all_users()
            
            for user in users:
                uid = user.id
                current_freq = int(settings_uc.get_frequency(uid))
                
                if uid not in user_frequencies or user_frequencies[uid] != current_freq:
                    logging.info(f"Configuring scheduler for User {uid} -> Every {current_freq} minutes.")
                    
                    schedule.clear(str(uid))
                    schedule.every(current_freq).minutes.tag(str(uid)).do(run_job_hunter, user_id=uid)
                    
                    if uid not in user_frequencies:
                        run_job_hunter(uid)
                        
                    user_frequencies[uid] = current_freq
                    
            active_uids = [u.id for u in users]
            for tracked_uid in list(user_frequencies.keys()):
                if tracked_uid not in active_uids:
                    logging.info(f"Removing schedules for deleted user {tracked_uid}")
                    schedule.clear(str(tracked_uid))
                    del user_frequencies[tracked_uid]
                    
        except Exception as e:
            logging.error(f"Scheduler loop encountered an error: {e}")
            
        schedule.run_pending()
        time.sleep(60)
