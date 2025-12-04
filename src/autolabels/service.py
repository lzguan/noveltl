from sqlalchemy.orm import Session
from typing import Dict
from . import models
from ..auth.models import User

def insert_autolabels(db : Session, current_user : User, request : schemas.CreateAutoLabel) -> models.AutoLabel:
    pass


def autogenerate_labels_for_chapter_revision(db : Session, current_user : User, raw_chapter_revision_id : int) -> models.AutoLabel:
    pass