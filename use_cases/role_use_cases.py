from adapters.repositories.sqlite_repo import SQLiteRepository

class RoleUseCases:
    def __init__(self, repo: SQLiteRepository):
        self.repo = repo
        
    def get_all_roles(self, user_id):
        return self.repo.get_target_roles(user_id, active_only=False)
        
    def get_active_roles(self, user_id):
        return self.repo.get_target_roles(user_id, active_only=True)
        
    def add_role(self, user_id, role_name):
        return self.repo.add_target_role(user_id, role_name)
        
    def toggle_role_status(self, user_id, role_id, is_active: bool):
        self.repo.toggle_target_role(user_id, role_id, is_active)
        
    def delete_role(self, user_id, role_id):
        self.repo.delete_target_role(user_id, role_id)
