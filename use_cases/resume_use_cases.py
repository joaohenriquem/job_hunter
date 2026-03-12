# LAYER 2: Application Business Rules (Use Cases)
from adapters.repositories.sqlite_repo import SQLiteRepository

class ResumeUseCases:
    def __init__(self, repo: SQLiteRepository):
        self.repo = repo
        
    def get_resume(self, user_id):
        """Busca o currículo do usuário."""
        return self.repo.get_resume_by_user(user_id)
        
    def save_resume(self, user_id, resume_data: dict):
        """Atualiza ou cria os dados de perfil do usuário."""
        self.repo.upsert_resume(user_id, resume_data)
        return True
