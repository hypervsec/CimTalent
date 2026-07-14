from enum import Enum as PythonEnum
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.types import TypeEngine


def database_enum[EnumT: PythonEnum](enum_type: type[EnumT], name: str) -> SQLAlchemyEnum:
    """Create a portable enum storing Python enum values, not member names."""
    return SQLAlchemyEnum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


def mutable_json_list() -> TypeEngine[Any]:
    """Use JSONB on PostgreSQL and JSON on lightweight test databases."""
    return MutableList.as_mutable(JSON().with_variant(JSONB(), "postgresql"))


def mutable_json_dict() -> TypeEngine[Any]:
    """Use JSONB on PostgreSQL and JSON on lightweight test databases."""
    return MutableDict.as_mutable(JSON().with_variant(JSONB(), "postgresql"))
