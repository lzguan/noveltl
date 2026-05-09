"""
Pydantic schemas for User models
"""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from ..schemas import Model
from .constants import UserType


class User(Model):
    """
    Pydantic model for user information.

    Attributes:
        user_id: id of this user.
        user_name: Username for this user.
        user_type: A value in UserType (e.g. 'admin', or 'user')
    """

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    user_id: uuid.UUID
    user_name: str
    user_type: UserType


class CreateUser(Model):
    """
    Pydantic schema to validate data required to create a user.

    Attributes:
        user_name: Username of user being created.
        user_password: Unhashed password of user being create.
        user_type: UserType type of user to be created.
    Notes:

    """

    model_config = ConfigDict(use_enum_values=True)

    user_name: str
    user_password: str
    user_type: UserType

    @field_validator("user_name")
    @classmethod
    def validate_user_name(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long.")
        return v


class DeleteUserStatus(Model):
    """
    Pydantic schema to return status after deleting a user

    Attributes:
        status: One of 'success', 'fail', 'verify'.
        detail: String denoting details of operation.
    """

    status: Literal["success", "fail", "verify"]
    detail: str | None = None


class Token(BaseModel):
    """
    Pydantic schema for a JWT

    Attributes:
        access_token: Payload.
        token_type: Type of token.
    """

    access_token: str
    token_type: str
