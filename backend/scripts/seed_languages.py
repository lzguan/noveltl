from sqlalchemy import insert

from src.database import SessionLocal
from src.languages.models import Language

languages_to_seed = [
    {"language_code": "en", "language_name": "English"},
    {"language_code": "jp", "language_name": "Japanese"},
    {"language_code": "cn", "language_name": "Chinese"},
    {"language_code": "kr", "language_name": "Korean"},
]

with SessionLocal() as db:
    stmt = insert(Language).values(languages_to_seed)
    db.execute(stmt)
    db.commit()
    print("Language seeding completed.")
