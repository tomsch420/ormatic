from __future__ import annotations

import logging
from dataclasses import fields, is_dataclass
from functools import lru_cache
from typing import Optional, List

import sqlalchemy.inspection
import sqlalchemy.orm
from sqlalchemy import Column
from sqlalchemy.orm import MANYTOONE, DeclarativeBase, declared_attr, ONETOMANY, RelationshipProperty
from sqlalchemy.sql.schema import Table
from sqlalchemy.util import ReadOnlyProperties
from typing_extensions import Type, get_args, Dict, Any, TypeVar, Generic

from .utils import recursive_subclasses

logger = logging.getLogger(__name__)

T = TypeVar('T')
_DAO = TypeVar("_DAO", bound="DataAccessObject")


class NoGenericError(TypeError):
    def __init__(self, cls):
        super().__init__(f"Cannot determine original class for {cls.__name__!r}. "
                         "Did you forget to parameterise the DataAccessObject subclass?")


def is_data_column(column: Column):
    return not column.primary_key and len(column.foreign_keys) == 0 and column.name != "polymorphic_type"

class HasGeneric(Generic[T]):

    @classmethod
    @lru_cache(maxsize=None)
    def original_class(cls) -> Type:
        """
        :return: The original class of this DAO.
        """
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

class DataAccessObject(HasGeneric[T]):
    """
    This class defines the interfaces the DAO classes should implement.

    ORMatic generates classes from your python code that are derived from the provided classes in your package.
    The generated classes can be instantiated from objects of the given classes and vice versa.
    This class describes the necessary functionality.
    """


    @classmethod
    def to_dao(cls, obj: T, memo: Dict[int, Any] = None, register=True) -> _DAO:
        """
        Converts an object to its Data Access Object (DAO) equivalent using a class method. This method ensures that
        objects are not processed multiple times by utilizing a memoization technique. It also handles alternative
        mappings for objects and applies transformation logic based on class inheritance and mapping requirements.

        :param obj: Object to be converted into its DAO equivalent
        :param memo: Dictionary that keeps track of already converted objects to avoid duplicate processing.
            Defaults to None.
        :return: Instance of the DAO class (_DAO) that represents the input object after conversion
        """

        # check if the obj has been converted to a dao already
        if memo is None:
            memo = {}
        if id(obj) in memo:
            return memo[id(obj)]

        # apply alternative mapping if needed
        if issubclass(cls.original_class(), AlternativeMapping):
            obj = cls.original_class().to_dao(obj, memo=memo, )

        # get the primary inheritance route
        base = cls.__bases__[0]
        result = cls()

        # if the superclass of this dao is a DAO for an alternative mapping
        if issubclass(base, DataAccessObject) and issubclass(base.original_class(), AlternativeMapping):
            result.to_dao_if_subclass_of_alternative_mapping(obj=obj, memo=memo, base=base)
        else:
            result.to_dao_default(obj=obj, memo=memo)

        if register:
            memo[id(obj)] = result
        return result

    def to_dao_default(self, obj: T, memo: Dict[int, Any]):
        """
        Converts the given object into a Data Access Object (DAO) representation
        by extracting column and relationship data. This method is primarily used
        in ORM (Object-Relational Mapping) to transform a domain object into its mapped
        database representation.

        :param obj: The source object to be converted into a DAO representation.
        :param memo: A dictionary to handle cyclic references by tracking processed objects.
        """
        # Fill super class columns, Mapper-columns - self.columns
        mapper: sqlalchemy.orm.Mapper = sqlalchemy.inspection.inspect(type(self))

        # Create a new instance of the DAO class
        self.get_columns_from(obj=obj, columns=mapper.columns)
        self.get_relationships_from(obj=obj, relationships=mapper.relationships, memo=memo)

    def to_dao_if_subclass_of_alternative_mapping(self, obj: T, memo: Dict[int, Any], base: Type[DataAccessObject]):
        """
        Transforms the given object into a corresponding Data Access Object (DAO) if it is a
        subclass of an alternatively mapped entity. This involves processing both the inherited
        and subclass-specific attributes and relationships of the object.

        :param obj: The source object to be transformed into a DAO.
        :param memo: A dictionary used to handle circular references when transforming objects.
                     Typically acts as a memoization structure for keeping track of processed objects.
        :param base: The parent class type that defines the base mapping for the DAO.
        :return: None. The method directly modifies the DAO instance by populating it with attribute
                 and relationship data from the source object.
        """

        # create dao of alternatively mapped superclass
        parent_dao = base.original_class().to_dao(obj, memo=memo)

        # Fill super class columns
        parent_mapper = sqlalchemy.inspection.inspect(base)
        mapper: sqlalchemy.orm.Mapper = sqlalchemy.inspection.inspect(type(self))

        # split up the columns in columns defined by the parent and columns defined by this dao
        all_columns = mapper.columns
        columns_of_parent = parent_mapper.columns
        columns_of_this_table = [c for c in all_columns if c.name not in columns_of_parent]

        # copy values from superclass dao
        self.get_columns_from(parent_dao, columns_of_parent)

        # copy values that only occur in this dao
        self.get_columns_from(obj, columns_of_this_table)

        # split relationships in relationships by parent and relationships by child
        all_relationships = mapper.relationships
        relationships_of_parent = parent_mapper.relationships
        relationships_of_this_table = [r for r in all_relationships if r not in relationships_of_parent]

        for relationship in relationships_of_parent:
            setattr(self, relationship.key, getattr(parent_dao, relationship.key))

        self.get_relationships_from(obj, relationships_of_this_table, memo)

    def get_columns_from(self, obj: T, columns: List):
        """
        Retrieves and assigns values from specified columns of a given object.

        Iterates through a list of columns, and for each column that is identified
        as a data column, assigns its value from the given object to the current
        instance.

        :param obj: The object from which the column values are retrieved.
        :param columns: A list of columns to be processed.

        Raises:
            AttributeError: Raised if the provided object or column does not have
                the corresponding attribute during assignment.
        """
        for column in columns:
            if is_data_column(column):
                setattr(self, column.name, getattr(obj, column.name))

    def get_relationships_from(self, obj: T, relationships: List[RelationshipProperty],
                            memo: Dict[int, Any]):
        """
        Retrieve and update relationships from an object based on the given relationship
        properties. This function processes various types of relationships (e.g., one-to-one,
        one-to-many) and appropriately updates the current instance with corresponding
        DAO objects.

        :param obj: The source object containing relationships to be processed.
        :param relationships: A list of `RelationshipProperty` objects that define the
            relationships to be accessed from the source object.
        :param memo: A dictionary used to maintain references to already-processed objects
            to avoid duplications or cycles during DAO construction.
        :return: None
        """
        for relationship in relationships:

            # update one to one like relationships
            if (relationship.direction == MANYTOONE or
                    (relationship.direction == ONETOMANY and not relationship.uselist)):

                value_in_obj = getattr(obj, relationship.key)
                if value_in_obj is None:
                    dao_of_value = None
                else:
                    dao_class = get_dao_class(type(value_in_obj))
                    if dao_class is None:
                        raise ValueError(f"Class {type(value_in_obj)} does not have a DAO. This happened when trying"
                                         f"to create a dao for {obj}")
                    dao_of_value = dao_class.to_dao(value_in_obj, memo=memo)

                setattr(self, relationship.key, dao_of_value)

            # update one to many relationships (list of other objects)
            elif relationship.direction == ONETOMANY:
                result = []
                value_in_obj = getattr(obj, relationship.key)
                for v in value_in_obj:
                    result.append(get_dao_class(type(v)).to_dao(v, memo=memo))

                setattr(self, relationship.key, result)

    def from_dao(self, memo: Dict[int, Any] = None) -> T:
        """
        Create the original instance of this class from an instance of this DAO.
        If a different specification than the specification of the original class is needed, overload this method.

        :param memo: The memo dictionary to use for memoization.
        :return: An instance of this class created from the original class.
        """
        raise NotImplementedError


    def __repr__(self):
        mapper: sqlalchemy.orm.Mapper = sqlalchemy.inspection.inspect(type(self))
        kwargs = {}
        for column in mapper.columns:
            if is_data_column(column):
                kwargs[column.name] = repr(getattr(self, column.name))

        for relationship in mapper.relationships:
            value = getattr(self, relationship.key)
            kwargs[relationship.key] = repr(value)

        kwargs_str = ", ".join([f"{key}={value}" for key, value in kwargs.items()])

        result = f"{type(self).__name__}({kwargs_str})"
        return result

class AlternativeMapping(HasGeneric[T]):

    @classmethod
    def to_dao(cls, obj: T, memo: Dict[int, Any] = None) -> _DAO:
        """
        Create a DAO from the obj if it doesn't exist.

        :param obj: The obj to create the DAO from.
        :param memo: The memo dictionary to check for already build instances.

        :return: An instance of this class created from the obj.
        """
        if memo is None:
            memo = {}
        if id(obj) in memo:
            return memo[id(obj)]
        else:
            result = cls.create_instance(obj)
            memo[id(obj)] = result
            return result

    @classmethod
    def create_instance(cls, obj: T):
        """
        Create a DAO from the obj.
        The method needs to be overloaded by the user.

        :param obj: The obj to create the DAO from.
        :return: An instance of this class created from the obj.
        """
        raise NotImplementedError

@lru_cache(maxsize=None)
def get_dao_class(cls: Type) -> Optional[Type[DataAccessObject]]:
    if get_alternative_mapping(cls) is not None:
        cls = get_alternative_mapping(cls)
    for dao in recursive_subclasses(DataAccessObject):
        if dao.original_class() == cls:
            return dao
    return None

@lru_cache(maxsize=None)
def get_alternative_mapping(cls: Type) -> Optional[Type[DataAccessObject]]:
    for alt_mapping in recursive_subclasses(AlternativeMapping):
        if alt_mapping.original_class() == cls:
            return alt_mapping
    return None


def to_dao(obj: Any, memo: Dict[int, Any] = None) -> DataAccessObject:
    """
    Convert any object to a dao class.
    """
    return get_dao_class(type(obj)).to_dao(obj, memo)