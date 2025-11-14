"""This module provides global config variables."""

import os
from dotenv import load_dotenv

load_dotenv()

DB_HOST : str = os.getenv('DB_HOST')
DB_PORT : str = os.getenv('DB_PORT')
DB_USER : str = os.getenv('DB_USER')
DB_PASSWORD : str = os.getenv('DB_PASSWORD')
DB_NAME : str = os.getenv('DB_NAME')
DB_URL : str = os.getenv('DB_URL')
ADMIN_USERNAME : str = os.getenv('ADMIN_USERNAME')