from typing import Type, get_args, Dict, List, TextIO, Any
import inspect
import os
import types
from dataclasses import dataclass, fields, is_dataclass
from importlib import import_module

from sqlalchemy import Column, Table, Integer, String
from sqlalchemy.orm import MappedAsDataclass, registry, declared_attr, DeclarativeBase
from typing_extensions import TypeVar, Generic, Self, Optional, get_type_hints

T = TypeVar('T')


class DataAccessObject(Generic[T]):
    """
    This class defines the interfaces the DAO classes should implement.

    ORMatic generates classes from your python code that are derived from the provided classes in your package.
    The generated classes can be instantiated from objects of the given classes and vice versa.
    This class describes the necessary functionality.
    """

    @classmethod
    def original_class(cls) -> Type:
        # First check if we have a stored _original_class attribute (for dynamically created classes)
        if hasattr(cls, '_original_class'):
            return cls._original_class

        # Fall back to the original method for manually created classes
        try:
            base = cls.__orig_bases__[0]
            type_args = get_args(base)
            if not type_args:
                raise TypeError(
                    f"Cannot determine original class for {cls.__name__!r}. "
                    "Did you forget to parameterise the DataAccessObject subclass?"
                )
            return type_args[0]
        except (AttributeError, IndexError):
            raise TypeError(
                f"Cannot determine original class for {cls.__name__!r}. "
                "Did you forget to parameterise the DataAccessObject subclass?"
            )

    @classmethod
    def from_original_class(cls, original_instance: T, memo: Dict[int, Any] = None) -> Self:
        """
        Create an instance of this class from an instance of the original class.
        If a different specification than the specification of the original class is needed, overload this method.

        :return: An instance of this class created from the original class.
        """

        if memo is None:
            memo = {}
        if id(original_instance) in memo:
            return memo[id(original_instance)]

        if not is_dataclass(original_instance.__class__):
            raise TypeError(f"Original class {original_instance.__class__.__name__} must be a dataclass")

        # Get constructor parameters
        init_params = inspect.signature(cls.__init__).parameters
        init_param_names = set(init_params.keys()) - {'self'}

        # Get field values from original instance
        field_values = {}
        for f in fields(original_instance.__class__):
            # Only include fields that are accepted by the constructor
            if f.name in init_param_names or f.name not in init_param_names and hasattr(cls, f.name):
                field_values[f.name] = getattr(original_instance, f.name)

        # Add id field with default value if not present and accepted by constructor
        if 'id' not in field_values and 'id' in init_param_names:
            field_values['id'] = None

        # Create new instance with field values
        return cls(**field_values)

    def to_original_class(self, memo: Dict[int, Any] = None) -> T:
        """
        :return: An instance of this class created from the original class.
        """

        if memo is None:
            memo = {}
        if id(self) in memo:
            return memo[id(self)]

        original_cls = self.original_class()

        # Get constructor parameters
        init_params = inspect.signature(original_cls.__init__).parameters
        init_param_names = set(init_params.keys()) - {'self'}

        # Get field values from this instance
        field_values = {}
        for f in fields(original_cls):
            # Only include fields that are accepted by the constructor
            if f.name in init_param_names and hasattr(self, f.name):
                field_values[f.name] = getattr(self, f.name)

        # Create new instance with field values
        return original_cls(**field_values)

# inheritance
# foreign keys
# something like ORMexplcitmapping
# insert die das og objekt reinimmt
# get from database die das og objekt rausgibt