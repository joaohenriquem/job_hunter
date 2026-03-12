from dataclasses import dataclass

@dataclass
class TargetRole:
    id: int
    user_id: int
    role_name: str
    is_active: bool
    added_at: str
