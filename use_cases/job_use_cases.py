from adapters.repositories.sqlite_repo import SQLiteRepository

class JobUseCases:
    def __init__(self, repo: SQLiteRepository):
        self.repo = repo
        
    def get_jobs_dataframe(self, user_id):
        """Returns a Pandas DataFrame formatted for the UI."""
        return self.repo.load_jobs_df(user_id)
        
    def get_runs_dataframe(self, user_id):
        return self.repo.load_runs_df(user_id)
        
    def delete_job(self, user_id, job_id):
        self.repo.delete_job(user_id, job_id)
        
    def mark_job_applied(self, user_id, job_id, applied: bool):
        self.repo.set_job_applied(user_id, job_id, applied)
        
    def mark_job_invalid(self, user_id, job_id, invalid: bool):
        self.repo.set_job_invalid(user_id, job_id, invalid)
        
    def update_job_status(self, user_id, job_id, status: str):
        self.repo.set_job_status(user_id, job_id, status)
        
    def update_job_rating(self, user_id, job_id, rating: int):
        self.repo.set_job_rating(user_id, job_id, rating)
