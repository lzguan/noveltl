from ..config import auth_settings

SECRET_KEY : str = auth_settings.SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = 30
ALGORITHM = "HS256"
