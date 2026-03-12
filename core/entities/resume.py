from dataclasses import dataclass
from typing import Optional

@dataclass
class Resume:
    id: Optional[int]
    user_id: int
    full_name: str
    email: str
    phone: str
    linkedin: str
    portfolio: str
    professional_summary: str
    experience: str
    education: str
    skills: str
    languages: str
