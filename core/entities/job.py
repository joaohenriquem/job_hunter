from dataclasses import dataclass

@dataclass
class Job:
    id: int
    user_id: int
    role: str
    title: str
    url: str
    email: str
    company: str
    description: str
    is_home_office: bool
    apply_link: str
    discovered_at: str
    applied: bool = False
    is_invalid: bool = False
    application_status: str = 'Enviado'
    company_rating: int = 0
