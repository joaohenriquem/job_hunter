from dataclasses import dataclass

@dataclass
class User:
    id: int
    email: str
    password_hash: str
    created_at: str
