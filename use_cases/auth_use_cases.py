import json
from adapters.repositories.sqlite_repo import SQLiteRepository

class AuthUseCases:
    def __init__(self, repo: SQLiteRepository):
        self.repo = repo
        
    def login_local(self, email, password):
        if not email or not password:
            return None
        return self.repo.authenticate_user(email, password)
        
    def register_local(self, email, password):
        if not email or not password:
            return None
        return self.repo.create_user(email, password)
        
    def login_oauth(self, email):
        if not email:
            return None
        return self.repo.get_or_create_oauth_user(email)
        
    def get_all_users(self):
        return self.repo.get_all_users()

class SettingsUseCases:
    def __init__(self, repo: SQLiteRepository):
        self.repo = repo
        
    def get_countries(self, user_id):
        val = self.repo.get_setting(user_id, 'search_country', '["Brasil"]')
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
            return [str(parsed)]
        except:
            return [val]
        
    def set_countries(self, user_id, countries_list):
        if not countries_list:
            countries_list = ["Brasil"]
        self.repo.set_setting(user_id, 'search_country', json.dumps(countries_list))
        
    def get_frequency(self, user_id):
        return self.repo.get_setting(user_id, 'search_frequency_minutes', '60')
        
    def set_frequency(self, user_id, minutes):
        self.repo.set_setting(user_id, 'search_frequency_minutes', str(minutes))
