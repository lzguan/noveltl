"""Local evaluation tools for the NovelTL memory agent."""

from pathlib import Path

from dotenv import load_dotenv

# Package initialization precedes CLI imports that instantiate backend settings.
# Never search parent directories or replace Compose-provided environment values.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
