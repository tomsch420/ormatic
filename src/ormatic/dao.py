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


class Base(DeclarativeBase):
    """Base class for all declarative models"""
    pass


class DataAccessObject(Generic[T]):
    """
    This class defines the interfaces the DAO classes should implement.

    ORMatic generates classes from your python code that are derived from the provided classes in your package.
    The generated classes can be instantiated from objects of the given classes and vice versa.
    This class describes the necessary functionality.
    """
    id: int

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
    def from_original_class(cls, original_instance: T) -> Self:
        """
        Create an instance of this class from an instance of the original class.
        If a different specification than the specification of the original class is needed, overload this method.

        :return: An instance of this class created from the original class.
        """
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

    def to_original_class(self) -> T:
        """
        :return: An instance of this class created from the original class.
        """
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


class ORMatic2:
    """
    Class that takes in a bunch of classes and creates DAOs for them that allow database interaction.
    """

    def __init__(self, classes: List[Type], mapper_registry: Optional[registry] = None):
        """
        Initialize ORMatic2 with a list of classes to convert to DAOs.

        :param classes: List of classes to convert to DAOs
        :param mapper_registry: Optional SQLAlchemy registry, will create one if not provided
        """
        self.classes = classes
        self.mapper_registry = mapper_registry or registry()
        self.dao_classes: Dict[Type, Type] = {}

        # Create a declarative base with our registry
        self.Base = type('Base', (DeclarativeBase,), {'registry': self.mapper_registry})

        # Generate DAO classes
        for cls in self.classes:
            self.dao_classes[cls] = self._create_dao_class(cls)

    def _create_dao_class(self, cls: Type) -> Type:
        """
        Create a DAO class for the given class.

        :param cls: The class to create a DAO for
        :return: The created DAO class
        """
        if not is_dataclass(cls):
            raise TypeError(f"Class {cls.__name__} must be a dataclass")

        # Create class attributes
        attrs = {
            '__tablename__': cls.__name__,
            'id': Column(Integer, primary_key=True),
        }

        # Add fields from original class with SQLAlchemy Column definitions
        for f in fields(cls):
            field_type = get_type_hints(cls)[f.name]

            # Simple type mapping - could be expanded
            if field_type == int:
                col_type = Integer
            elif field_type == str:
                col_type = String(255)
            else:
                # Default to String for complex types
                col_type = String(255)

            attrs[f.name] = Column(col_type)

        # Create the DAO class
        dao_class_name = f"{cls.__name__}DAO"

        # Create a new class that inherits from Base and DataAccessObject
        bases = (self.Base, DataAccessObject[cls])
        dao_class = types.new_class(dao_class_name, bases, {}, lambda ns: ns.update(attrs))

        # Store the original class for use by original_class method
        dao_class._original_class = cls

        return dao_class

    def to_python_file(self, file_path: str) -> None:
        """
        Write the generated DAO classes to a Python file.

        :param file_path: Path to the file to write
        """
        with open(file_path, 'w') as f:
            # Write imports
            f.write("from dataclasses import dataclass, fields\n")
            f.write("from sqlalchemy.orm import MappedAsDataclass, DeclarativeBase, registry, mapped_column\n")
            f.write("from sqlalchemy import Integer, String\n")
            f.write("from ormatic.dao import DataAccessObject\n")
            f.write("import inspect\n\n")

            # Write original class imports
            modules = set()
            for cls in self.classes:
                modules.add(cls.__module__)

            for module in modules:
                f.write(f"from {module} import ")
                module_classes = [cls.__name__ for cls in self.classes if cls.__module__ == module]
                f.write(", ".join(module_classes))
                f.write("\n")

            f.write("\n\n# Create registry and base class\n")
            f.write("mapper_registry = registry()\n")
            f.write("class Base(MappedAsDataclass, DeclarativeBase):\n")
            f.write("    registry = mapper_registry\n\n")

            # Write DAO classes
            for original_cls, dao_cls in self.dao_classes.items():
                f.write(f"class {dao_cls.__name__}(Base, MappedAsDataclass, DataAccessObject[{original_cls.__name__}]):\n")
                f.write(f"    __tablename__ = '{original_cls.__name__}'\n")
                f.write("    id: int = mapped_column(Integer, primary_key=True)\n")

                # Write fields
                for field in fields(original_cls):
                    type_hint = get_type_hints(original_cls)[field.name]
                    if type_hint == int:
                        py_type = "int"
                        col_type = "Integer"
                    elif type_hint == str:
                        py_type = "str"
                        col_type = "String(255)"
                    else:
                        py_type = "str"
                        col_type = "String(255)"

                    f.write(f"    {field.name}: {py_type} = mapped_column({col_type})\n")

    def get_dao_class(self, cls: Type) -> Type:
        """
        Get the DAO class for a given original class.

        :param cls: The original class
        :return: The corresponding DAO class
        """
        if cls not in self.dao_classes:
            raise KeyError(f"No DAO class found for {cls.__name__}")
        return self.dao_classes[cls]

# inheritance
# foreign keys
# something like ORMexplcitmapping
# insert die das og objekt reinimmt
# get from database die das og objekt rausgibt