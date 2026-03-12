import logging
from datetime import datetime
import hashlib
import uuid
import sqlite3
import pandas as pd
from infrastructure.database.connection import get_connection
from core.entities.user import User
from core.entities.job import Job
from core.entities.role import TargetRole

logger = logging.getLogger(__name__)

class SQLiteRepository:
    def __init__(self):
        self._init_db()

    def _hash_password(self, password):
        SALT = "job_hunter_v2_salt_"
        return hashlib.sha256((SALT + password).encode('utf-8')).hexdigest()

    def _init_db(self):
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                password_hash TEXT,
                created_at TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT,
                title TEXT,
                url TEXT,
                email TEXT,
                company TEXT,
                description TEXT,
                is_home_office BOOLEAN,
                apply_link TEXT,
                discovered_at TIMESTAMP,
                applied BOOLEAN DEFAULT 0,
                is_invalid BOOLEAN DEFAULT 0,
                UNIQUE(user_id, url),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                timestamp TIMESTAMP,
                roles_searched TEXT,
                new_jobs_found INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS target_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role_name TEXT COLLATE NOCASE,
                is_active BOOLEAN DEFAULT 1,
                added_at TIMESTAMP,
                UNIQUE(user_id, role_name),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER,
                key TEXT,
                value TEXT,
                PRIMARY KEY(user_id, key),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                full_name TEXT,
                email TEXT,
                phone TEXT,
                linkedin TEXT,
                portfolio TEXT,
                professional_summary TEXT,
                experience TEXT,
                education TEXT,
                skills TEXT,
                languages TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        conn.commit()
        
        # --- MIGRATIONS ---
        try:
            cursor.execute("ALTER TABLE jobs ADD COLUMN application_status TEXT DEFAULT 'Enviado'")
        except sqlite3.OperationalError:
            pass # Column already exists
            
        try:
            cursor.execute("ALTER TABLE jobs ADD COLUMN company_rating INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass # Column already exists
            
        conn.commit()
        conn.close()

    # --- USER AUTHENTICATION ---
    def create_user(self, email, password):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                           (email.strip().lower(), self._hash_password(password), datetime.now().isoformat()))
            conn.commit()
            user_id = cursor.lastrowid
            self.set_setting(user_id, 'search_country', '["Brasil"]')
            self.set_setting(user_id, 'search_frequency_minutes', '60')
            return user_id
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()

    def authenticate_user(self, email, password):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash FROM users WHERE email = ?", (email.strip().lower(),))
        row = cursor.fetchone()
        conn.close()
        if row and row[1] == self._hash_password(password):
            return row[0]
        return None

    def get_or_create_oauth_user(self, email):
        conn = get_connection()
        cursor = conn.cursor()
        email_clean = email.strip().lower()
        
        cursor.execute("SELECT id FROM users WHERE email = ?", (email_clean,))
        row = cursor.fetchone()
        
        if row:
            conn.close()
            return row[0]
            
        dummy_pass = str(uuid.uuid4())
        cursor.execute("INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                       (email_clean, self._hash_password(dummy_pass), datetime.now().isoformat()))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        self.set_setting(user_id, 'search_country', '["Brasil"]')
        self.set_setting(user_id, 'search_frequency_minutes', '60')
        
        return user_id

    def get_all_users(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, password_hash, created_at FROM users")
        rows = cursor.fetchall()
        conn.close()
        return [User(*row) for row in rows]

    # --- SETTINGS ---
    def get_setting(self, user_id, key, default_value=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE user_id = ? AND key = ?', (user_id, key))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else default_value

    def set_setting(self, user_id, key, value):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO settings (user_id, key, value) 
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value
        ''', (user_id, key, str(value)))
        conn.commit()
        conn.close()

    # --- TARGET ROLES ---
    def get_target_roles(self, user_id, active_only=True):
        conn = get_connection()
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT id, user_id, role_name, is_active, added_at FROM target_roles WHERE user_id = ? AND is_active = 1", (user_id,))
        else:
            cursor.execute("SELECT id, user_id, role_name, is_active, added_at FROM target_roles WHERE user_id = ?", (user_id,))
        result = cursor.fetchall()
        conn.close()
        return [TargetRole(*row) for row in result]

    def add_target_role(self, user_id, role_name):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO target_roles (user_id, role_name, added_at)
                VALUES (?, ?, ?)
            ''', (user_id, role_name, datetime.now().isoformat()))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def toggle_target_role(self, user_id, role_id, is_active):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE target_roles SET is_active = ? WHERE id = ? AND user_id = ?', (is_active, role_id, user_id))
        conn.commit()
        conn.close()

    def delete_target_role(self, user_id, role_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM target_roles SET is_active = ? WHERE id = ? AND user_id = ?', (False, role_id, user_id))  # Soft delete logic? Let's keep hard delete from before.
        cursor.execute('DELETE FROM target_roles WHERE id = ? AND user_id = ?', (role_id, user_id))
        conn.commit()
        conn.close()

    # --- JOBS ---
    def load_jobs_df(self, user_id):
        conn = get_connection()
        query = f"SELECT * FROM jobs WHERE user_id = {user_id} ORDER BY discovered_at DESC"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def get_jobs(self, user_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM jobs WHERE user_id = ? ORDER BY discovered_at DESC', (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [Job(*row) for row in rows]

    def insert_job(self, user_id, job_data):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO jobs (user_id, role, title, url, email, company, description, is_home_office, apply_link, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                job_data.get('Role'),
                job_data.get('Title'),
                job_data.get('URL'),
                job_data.get('Email'),
                job_data.get('Company'),
                job_data.get('Description'),
                job_data.get('Home Office') == 'Yes',
                job_data.get('Apply Link'),
                datetime.now().isoformat()
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def set_job_applied(self, user_id, job_id, applied_status):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE jobs SET applied = ? WHERE id = ? AND user_id = ?', (int(bool(applied_status)), int(job_id), int(user_id)))
        conn.commit()
        conn.close()

    def set_job_invalid(self, user_id, job_id, invalid_status):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE jobs SET is_invalid = ? WHERE id = ? AND user_id = ?', (int(bool(invalid_status)), int(job_id), int(user_id)))
        conn.commit()
        conn.close()
        
    def set_job_status(self, user_id, job_id, status: str):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE jobs SET application_status = ? WHERE id = ? AND user_id = ?', (str(status), int(job_id), int(user_id)))
        conn.commit()
        conn.close()
        
    def set_job_rating(self, user_id, job_id, rating: int):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE jobs SET company_rating = ? WHERE id = ? AND user_id = ?', (int(rating), int(job_id), int(user_id)))
        conn.commit()
        conn.close()

    def delete_job(self, user_id, job_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM jobs WHERE id = ? AND user_id = ?', (int(job_id), int(user_id)))
        conn.commit()
        conn.close()

    # --- RUNS ---
    def load_runs_df(self, user_id):
        conn = get_connection()
        query = f"SELECT * FROM runs WHERE user_id = {user_id} ORDER BY timestamp DESC LIMIT 50"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def log_run(self, user_id, roles, jobs_found):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO runs (user_id, timestamp, roles_searched, new_jobs_found)
            VALUES (?, ?, ?, ?)
        ''', (
            user_id,
            datetime.now().isoformat(),
            ", ".join(roles),
            jobs_found
        ))
        conn.commit()
        conn.close()

    # --- RESUME BUILDER ---
    def get_resume_by_user(self, user_id):
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM resumes WHERE user_id = ?", (int(user_id),))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            from core.entities.resume import Resume
            return Resume(
                id=row['id'],
                user_id=row['user_id'],
                full_name=row['full_name'],
                email=row['email'],
                phone=row['phone'],
                linkedin=row['linkedin'],
                portfolio=row['portfolio'],
                professional_summary=row['professional_summary'],
                experience=row['experience'],
                education=row['education'],
                skills=row['skills'],
                languages=row['languages']
            )
        return None

    def upsert_resume(self, user_id, resume_data: dict):
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute("SELECT id FROM resumes WHERE user_id = ?", (int(user_id),))
        row = cursor.fetchone()
        
        if row:
            # Update
            cursor.execute('''
                UPDATE resumes SET 
                    full_name=?, email=?, phone=?, linkedin=?, portfolio=?, 
                    professional_summary=?, experience=?, education=?, 
                    skills=?, languages=?
                WHERE user_id=?
            ''', (
                resume_data.get('full_name', ''), resume_data.get('email', ''), 
                resume_data.get('phone', ''), resume_data.get('linkedin', ''), 
                resume_data.get('portfolio', ''), resume_data.get('professional_summary', ''), 
                resume_data.get('experience', ''), resume_data.get('education', ''), 
                resume_data.get('skills', ''), resume_data.get('languages', ''),
                int(user_id)
            ))
        else:
            # Insert
            cursor.execute('''
                INSERT INTO resumes (
                    user_id, full_name, email, phone, linkedin, portfolio,
                    professional_summary, experience, education, skills, languages
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                int(user_id), resume_data.get('full_name', ''), resume_data.get('email', ''), 
                resume_data.get('phone', ''), resume_data.get('linkedin', ''), 
                resume_data.get('portfolio', ''), resume_data.get('professional_summary', ''), 
                resume_data.get('experience', ''), resume_data.get('education', ''), 
                resume_data.get('skills', ''), resume_data.get('languages', '')
            ))
            
        conn.commit()
        conn.close()
