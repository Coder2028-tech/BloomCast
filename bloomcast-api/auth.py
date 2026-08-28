import secrets
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

active_tokens: dict[str, int] = {}

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)

def create_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    active_tokens[token] = user_id
    return token

def get_user_id_from_token(token: str) -> int | None:
    return active_tokens.get(token)