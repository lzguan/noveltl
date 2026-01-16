"""
Todo: use argparse.
"""

import getpass

from src.auth.constants import UserType
from src.auth.models import User
from src.auth.utils import hash_password
from src.database import SessionLocal

username = input("Enter admin username: ")
password = getpass.getpass("Enter admin password: ")

with SessionLocal() as db:
    admin_user = User(
        user_name=username,
        user_type=UserType.ADMIN,
        user_hashed_password=hash_password(password)
    )
    db.add(admin_user)
    db.commit()
    print(f"Admin user '{username}' created successfully.")
