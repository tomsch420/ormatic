from __future__ import annotations
import inspect
from dataclasses import fields, is_dataclass
from functools import lru_cache

from typing_extensions import Type, get_args, Dict, Any, Self, TypeVar, Generic

T = TypeVar('T')
_DAO = TypeVar("_DAO", bound="DataAccessObject")

class NoGenericError(TypeError):
    def __init__(self, cls):
        super().__init__(f"Cannot determine original class for {cls.__name__!r}. "
                    "Did you forget to parameterise the DataAccessObject subclass?")

class DataAccessObject(Generic[T]):
    """
    This class defines the interfaces the DAO classes should implement.

    ORMatic generates classes from your python code that are derived from the provided classes in your package.
    The generated classes can be instantiated from objects of the given classes and vice versa.
    This class describes the necessary functionality.
    """

    @classmethod
    @lru_cache(maxsize=None)
    def original_class(cls) -> Type:
        """
        :return: The original class of this DAO.
        """
        # First check if we have a stored _original_class attribute (for dynamically created classes)
        if hasattr(cls, '_original_class'):
            return cls._original_class

        # Fall back to the original method for manually created classes
        try:
            # Look for DataAccessObject in the class's MRO (Method Resolution Order)
            for base_cls in cls.__mro__:
                if base_cls is DataAccessObject:
                    # Found DataAccessObject, now find the generic parameter
                    for base in cls.__orig_bases__:
                        if hasattr(base, "__origin__") and base.__origin__ is DataAccessObject:
                            type_args = get_args(base)
                            if type_args:
                                return type_args[0]

            # If we get here, we didn't find a DataAccessObject base with a generic parameter
            # Try the original approach as a fallback
            for base in getattr(cls, "__orig_bases__", []):
                type_args = get_args(base)
                if type_args:
                    return type_args[0]

            raise NoGenericError(cls)
        except (AttributeError, IndexError):
            raise NoGenericError(cls)

    @classmethod
    def to_dao(cls, obj: T, memo: Dict[int, Any] = None) -> _DAO:
        """
        Create an instance of this class from an instance of the original class.
        This method checks the fields in the DAO and tries to copy the value from `obj`.
        If the type of the field in this class is another DAO, the construction recurses into the type.

        If a different specification than the specification of the original class is needed, overload this method.


        :param obj: The instance of the original class.
        :param memo: The memo dictionary to use for memoization.
        :return: An instance of this class created from the original class.
        """

        if memo is None:
            memo = {}
        if id(obj) in memo:
            return memo[id(obj)]

        # Create a new instance of the DAO class
        dao_instance = cls()
        memo[id(obj)] = dao_instance

        # If the original object is a dataclass, copy its fields to the DAO
        if is_dataclass(obj):
            for field in fields(obj):
                field_name = field.name
                field_value = getattr(obj, field_name)

                # Skip fields that don't exist in the DAO
                if not hasattr(dao_instance, field_name):
                    continue

                # Handle nested objects
                if field_value is not None:
                    # Handle lists/containers
                    if isinstance(field_value, list):
                        # Skip empty lists
                        if not field_value:
                            continue

                        # Check if the items are dataclasses or simple types
                        if is_dataclass(field_value[0]):
                            # Find the appropriate DAO class for the items
                            item_dao_class = None
                            for subclass in cls.__subclasses__():
                                if subclass.original_class() == type(field_value[0]):
                                    item_dao_class = subclass
                                    break

                            if item_dao_class:
                                # Convert each item to a DAO
                                dao_list = [item_dao_class.to_dao(item, memo) for item in field_value]
                                setattr(dao_instance, field_name, dao_list)
                        else:
                            # For lists of simple types, just copy the list
                            setattr(dao_instance, field_name, field_value)
                    # Handle nested dataclasses
                    elif is_dataclass(field_value):
                        # Find the appropriate DAO class for the field
                        field_dao_class = None
                        for subclass in cls.__subclasses__():
                            if subclass.original_class() == type(field_value):
                                field_dao_class = subclass
                                break

                        if field_dao_class:
                            # Convert the field to a DAO
                            field_dao = field_dao_class.to_dao(field_value, memo)
                            setattr(dao_instance, field_name, field_dao)
                    else:
                        # For simple types, just copy the value
                        setattr(dao_instance, field_name, field_value)
                else:
                    # For None values, just copy None
                    setattr(dao_instance, field_name, None)

        return dao_instance

    def from_dao(self, memo: Dict[int, Any] = None) -> T:
        """
        Create the original instance of this class from an instance of this DAO.
        If a different specification than the specification of the original class is needed, overload this method.

        :param memo: The memo dictionary to use for memoization.
        :return: An instance of this class created from the original class.
        """

        if memo is None:
            memo = {}
        if id(self) in memo:
            return memo[id(self)]

        # Get the original class based on the actual type of the DAO object
        original_cls = type(self).original_class()

        # Create a dictionary to hold the constructor arguments
        constructor_args = {}

        # If the original class is a dataclass, prepare the constructor arguments
        if is_dataclass(original_cls):
            for field in fields(original_cls):
                field_name = field.name

                # Skip fields that don't exist in the DAO
                if not hasattr(self, field_name):
                    continue

                field_value = getattr(self, field_name)

                # Handle nested objects
                if field_value is not None:
                    # Handle lists/containers
                    if isinstance(field_value, list):
                        # Skip empty lists
                        if not field_value:
                            constructor_args[field_name] = field.default_factory() if hasattr(field, 'default_factory') else []
                            continue

                        # Check if the items are DAOs
                        if isinstance(field_value[0], DataAccessObject):
                            # Convert each DAO to an original object
                            original_list = [item.from_dao(memo) for item in field_value]
                            constructor_args[field_name] = original_list
                        else:
                            # For lists of simple types, just copy the list
                            constructor_args[field_name] = field_value
                    # Handle nested DAOs
                    elif isinstance(field_value, DataAccessObject):
                        # Convert the DAO to an original object
                        original_obj = field_value.from_dao(memo)
                        constructor_args[field_name] = original_obj
                    else:
                        # For simple types, just copy the value
                        constructor_args[field_name] = field_value
                else:
                    # For None values, just copy None
                    constructor_args[field_name] = None

            # Create a new instance of the original class
            original_instance = original_cls(**constructor_args)
            memo[id(self)] = original_instance
            return original_instance
        else:
            # If the original class is not a dataclass, try to create it with no arguments
            original_instance = original_cls()
            memo[id(self)] = original_instance
            return original_instance
