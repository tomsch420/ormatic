import importlib
from typing import Type, Optional

from sqlalchemy import TypeDecorator
from sqlalchemy import types

class TypeType(TypeDecorator):
    """
    Type that casts fields that are of type `type` to their class name on serialization and converts the name
    to the class itself through the globals on load.
    """
    impl = types.String(256)

    def process_bind_param(self, value: Type, dialect):
        return value.__module__ + "." + value.__name__

    def process_result_value(self, value: impl, dialect) -> Optional[Type]:
        if value is None:
            return None

        module_name, class_name = str(value).rsplit('.', 1)
        module = importlib.import_module(module_name)
        return getattr(module, class_name)
