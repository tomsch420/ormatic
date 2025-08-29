from __future__ import annotations

import inspect
import logging
import threading
from functools import lru_cache
from typing import Optional, List

import sqlalchemy.inspection
import sqlalchemy.orm
from sqlalchemy import Column
from sqlalchemy.orm import MANYTOONE, ONETOMANY, RelationshipProperty
from typing_extensions import Type, get_args, Dict, Any, TypeVar, Generic

from .utils import recursive_subclasses

logger = logging.getLogger(__name__)
_repr_thread_local = threading.local()

T = TypeVar('T')
_DAO = TypeVar("_DAO", bound="DataAccessObject")


class NoGenericError(TypeError):
    """
    Exception raised when the original class for a DataAccessObject subclass cannot
    be determined.

    This exception is typically raised when a DataAccessObject subclass has not
    been parameterized properly, which prevents identifying the original class
    associated with it.
    """

    def __init__(self, cls):
        super().__init__(f"Cannot determine original class for {cls.__name__!r}. "
                         "Did you forget to parameterise the DataAccessObject subclass?")


class NoDAOFoundError(TypeError):
    """
    Represents an error raised when no DAO (Data Access Object) class is found for a given class.

    This exception is typically used when an attempt to convert a class into a corresponding DAO fails.
    It provides information about the class and the DAO involved.
    """

    obj: Any
    """
    The class that no dao was found for
    """

    def __init__(self, obj: Any):
        self.obj = obj
        super().__init__(f"Class {type(obj)} does not have a DAO.")


class NoDAOFoundDuringParsingError(NoDAOFoundError):
    dao: Type
    """
    The DAO class that tried to convert the cls to a DAO if any.
    """

    relationship: RelationshipProperty

    def __init__(self, obj: Any, dao: Type, relationship: RelationshipProperty = None):
        self.obj = obj
        self.dao = dao
        self.relationship = relationship
        TypeError.__init__(self, f"Class {type(obj)} does not have a DAO. This happened when trying"
                                 f"to create a dao for {dao}) on the relationship {relationship} with the "
                                 f"relationship value {obj}."
                                 f"Expected a relationship value of type {relationship.target}.")


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
    def to_dao(cls, obj: T, memo: Dict[int, Any] = None, keep_alive: Dict[int, Any] = None, register=True) -> _DAO:
        """
        Converts an object to its Data Access Object (DAO) equivalent using a class method. This method ensures that
        objects are not processed multiple times by using a memoization technique. It also handles alternative
        mappings for objects and applies transformation logic based on class inheritance and mapping requirements.

        :param obj: Object to be converted into its DAO equivalent
        :param memo: Dictionary that keeps track of already converted objects to avoid duplicate processing.
            Defaults to None.
        :param keep_alive: Dictionary to keep track of objects that should not be garbage collected during the conversion.
            Defaults to None.
        :param register: Whether to register the DAO class in the memo.
        :return: Instance of the DAO class (_DAO) that represents the input object after conversion
        """

        # check if the obj has been converted to a dao already
        if memo is None:
            memo = {}

        if keep_alive is None:
            keep_alive = {}

        original_obj_id = id(obj)
        if id(obj) in memo:
            result = memo[id(obj)]

            # if the object is not the correct one (could happend when ids are reassigned)
            if not isinstance(result, cls):
                del memo[id(obj)]
                # raise ValueError(f"Expected result to be of type {cls} but got {result}")
            else:
                return memo[id(obj)]

        # apply alternative mapping if needed
        if issubclass(cls.original_class(), AlternativeMapping):
            dao_obj = cls.original_class().to_dao(obj, memo=memo, keep_alive=keep_alive)
        else:
            dao_obj = obj

        # get the primary inheritance route
        base = cls.__bases__[0]
        result = cls()

        # register the result as in process
        if register:
            #memo[id(obj)] = result
            memo[original_obj_id] = result
            keep_alive[original_obj_id] = obj

        # if the superclass of this dao is a DAO for an alternative mapping
        if issubclass(base, DataAccessObject) and issubclass(base.original_class(), AlternativeMapping):
            result.to_dao_if_subclass_of_alternative_mapping(obj=dao_obj, memo=memo, keep_alive=keep_alive, base=base)
        else:
            result.to_dao_default(obj=dao_obj, memo=memo, keep_alive=keep_alive)

        return result

    def to_dao_default(self, obj: T, memo: Dict[int, Any], keep_alive: Dict[int, Any]):
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
        self.get_relationships_from(obj=obj, relationships=mapper.relationships, memo=memo, keep_alive=keep_alive)

    def to_dao_if_subclass_of_alternative_mapping(self, obj: T, memo: Dict[int, Any], keep_alive: Dict[int, Any],
                                                  base: Type[DataAccessObject]):
        """
        Transforms the given object into a corresponding Data Access Object (DAO) if it is a
        subclass of an alternatively mapped entity. This involves processing both the inherited
        and subclass-specific attributes and relationships of the object.

        :param obj: The source object to be transformed into a DAO.
        :param memo: A dictionary used to handle circular references when transforming objects.
                     Typically acts as a memoization structure for keeping track of processed objects.
        :param keep_alive: A dictionary to ensure that objects remain in memory during the transformation
                          process, preventing them from being garbage collected prematurely.
        :param base: The parent class type that defines the base mapping for the DAO.
        :return: None. The method directly modifies the DAO instance by populating it with attribute
                 and relationship data from the source object.
        """

        # Temporarily remove the object from the memo dictionary to allow the parent DAO to be created
        temp_dao = None
        if id(obj) in memo:
            temp_dao = memo[id(obj)]
            del memo[id(obj)]

        # create dao of alternatively mapped superclass
        parent_dao = base.original_class().to_dao(obj, memo=memo, keep_alive=keep_alive)

        # Restore the object in the memo dictionary
        if temp_dao is not None:
            memo[id(obj)] = temp_dao

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

        self.get_relationships_from(obj, relationships_of_this_table, memo, keep_alive)

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

    def get_relationships_from(self, obj: T, relationships: List[RelationshipProperty], memo: Dict[int, Any],
                               keep_alive: Dict[int, Any]):
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
        :param keep_alive: A dictionary to ensure that objects remain in memory during the
            transformation process, preventing them from being garbage collected prematurely.
        :return: None
        """
        for relationship in relationships:

            # update one to one like relationships
            if (relationship.direction == MANYTOONE or (
                    relationship.direction == ONETOMANY and not relationship.uselist)):

                value_in_obj = getattr(obj, relationship.key)
                if value_in_obj is None:
                    dao_of_value = None
                else:
                    dao_class = get_dao_class(type(value_in_obj))
                    if dao_class is None:
                        raise NoDAOFoundDuringParsingError(value_in_obj, type(self), relationship)
                    dao_of_value = dao_class.to_dao(value_in_obj, memo=memo, keep_alive=keep_alive)

                setattr(self, relationship.key, dao_of_value)

            # update one to many relationships (list of other objects)
            elif relationship.direction == ONETOMANY:
                result = []
                value_in_obj = getattr(obj, relationship.key)
                for v in value_in_obj:
                    result.append(get_dao_class(type(v)).to_dao(v, memo=memo, keep_alive=keep_alive))

                setattr(self, relationship.key, result)

    def from_dao(self, memo: Dict[int, Any] = None, in_progress: Dict[int, bool] = None) -> T:
        """
        Converts the current Data Access Object (DAO) into its corresponding domain model
        representation. This method ensures that all scalar attributes and relationships
        defined for the DAO are properly mapped to the original domain model.

        :param memo: A dictionary used to maintain references to already-processed objects
                     to avoid duplications or cycles during DAO construction.
        :param in_progress: A dictionary used to track objects that are currently being processed
                            to detect circular dependencies.
        :return: The corresponding domain model representing the current Data Access Object
        """
        # Initialize dictionaries if they're None
        if memo is None:
            memo = {}
        if in_progress is None:
            in_progress = {}

        # Return early if already fully constructed
        if id(self) in memo:
            return memo[id(self)]

        # Phase 1: Allocate uninitialized object and memoize it immediately
        result = self.original_class().__new__(self.original_class())
        memo[id(self)] = result
        in_progress[id(self)] = True

        mapper: sqlalchemy.orm.Mapper = sqlalchemy.inspection.inspect(type(self))

        # get argument names of the original class
        kwargs = {}
        init_of_original_class = self.original_class().__init__
        argument_names = [p.name for p in inspect.signature(init_of_original_class).parameters.values()][1:]

        # get data columns
        for column in mapper.columns:
            if column.name not in argument_names:
                continue

            if is_data_column(column):
                kwargs[column.name] = getattr(self, column.name)

        # get relationships
        circular_refs = {}  # Store circular references to fix later
        for relationship in mapper.relationships:
            if relationship.key not in argument_names:
                continue

            value = getattr(self, relationship.key)

            # handle one-to-one relationships
            if (relationship.direction == MANYTOONE or (
                    relationship.direction == ONETOMANY and not relationship.uselist)):
                if value is None:
                    parsed = None
                else:
                    parsed = value.from_dao(memo=memo, in_progress=in_progress)
                    if parsed is memo.get(id(value)):
                        circular_refs[relationship.key] = value
                kwargs[relationship.key] = parsed

            # handle one-to-many relationships
            elif relationship.direction == ONETOMANY:
                if value:
                    og_instances = []
                    for v in value:
                        instance = v.from_dao(memo=memo, in_progress=in_progress)
                        if instance is memo.get(id(v)):
                            circular_refs.setdefault(relationship.key, []).append(v)
                        og_instances.append(instance)
                    kwargs[relationship.key] = type(value)(og_instances)
                else:
                    kwargs[relationship.key] = value
            else:
                raise NotImplementedError(f"Cannot parse relationship {relationship}")

        # if i am the child of an alternatively mapped parent
        base = self.__class__.__bases__[0]
        base_kwargs = {}
        if issubclass(base, DataAccessObject) and issubclass(base.original_class(), AlternativeMapping):

            # construct the super class from the super dao
            parent_dao = base()  # empty parent DAO
            parent_mapper = sqlalchemy.inspection.inspect(base)

            # copy scalar columns that the parent DAO is aware of
            for column in parent_mapper.columns:
                if is_data_column(column):
                    setattr(parent_dao, column.name, getattr(self, column.name))

            # copy relationships that the parent DAO is aware of
            for rel in parent_mapper.relationships:
                setattr(parent_dao, rel.key, getattr(self, rel.key))

            # now safely reconstruct the parent domain object
            base_result = parent_dao.from_dao(memo=memo, in_progress=in_progress)

            # fill the gaps from the base result into kwargs for __init__
            for argument in argument_names:
                if argument not in kwargs:
                    try:
                        base_kwargs[argument] = getattr(base_result, argument)
                    except AttributeError:
                        ...

        # Call the original __init__ to ensure proper initialization (e.g., default_factory fields)
        try:
            init_args = {**base_kwargs, **kwargs}
            result.__init__(**init_args)
        except TypeError as e:
            logging.getLogger(__name__).debug(f"from_dao __init__ call failed with {e}; falling back to manual assignment")
            for key, val in init_args.items():
                setattr(result, key, val)

        # Fix circular references
        for key, value in circular_refs.items():
            if isinstance(value, list):
                fixed_list = []
                for v in value:
                    fixed = memo.get(id(v))
                    fixed_list.append(fixed)
                setattr(result, key, fixed_list)
            else:
                fixed = memo.get(id(value))
                setattr(result, key, fixed)

        # If the result is an AlternativeMapping, we need to create the original object
        if isinstance(result, AlternativeMapping):
            # If the result has a create_from_dao method, call it to finalize the object creation
            result = result.create_from_dao()
            memo[id(self)] = result  # Update the memo with the final object

        # Done processing this object
        del in_progress[id(self)]

        return result

    def __repr__(self):
        if not hasattr(_repr_thread_local, 'seen'):
            _repr_thread_local.seen = set()

        if id(self) in _repr_thread_local.seen:
            return f"{self.__class__.__name__}(...)"

        _repr_thread_local.seen.add(id(self))
        try:
            mapper: sqlalchemy.orm.Mapper = sqlalchemy.inspection.inspect(type(self))
            kwargs = []
            for column in mapper.columns:
                value = getattr(self, column.name)
                if is_data_column(column):
                    kwargs.append(f"{column.name}={repr(value)}")

            for relationship in mapper.relationships:
                value = getattr(self, relationship.key)
                if value is not None:
                    if isinstance(value, list):
                        kwargs.append(f"{relationship.key}=[{', '.join(repr(v) for v in value)}]")
                    else:
                        kwargs.append(f"{relationship.key}={repr(value)}")
                else:
                    kwargs.append(f"{relationship.key}=None")

            return f"{self.__class__.__name__}({', '.join(kwargs)})"
        finally:
            _repr_thread_local.seen.remove(id(self))


class AlternativeMapping(HasGeneric[T]):

    @classmethod
    def to_dao(cls, obj: T, memo: Dict[int, Any] = None, keep_alive: Dict[int, Any] = None) -> _DAO:
        """
        Create a DAO from the obj if it doesn't exist.

        :param obj: The obj to create the DAO from.
        :param memo: The memo dictionary to check for already build instances.
        :param keep_alive: The keep_alive dictionary to keep the object alive during the conversion.

        :return: An instance of this class created from the obj.
        """
        if memo is None:
            memo = {}
        if id(obj) in memo:
            return memo[id(obj)]
        elif isinstance(obj, cls):
            return obj
        else:
            result = cls.create_instance(obj)
            # memo[id(obj)] = result
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

    def create_from_dao(self) -> T:
        """
        Creates an object from a Data Access Object (DAO) by utilizing the predefined
        logic and transformations specific to the implementation. This facilitates
        constructing domain-specific objects from underlying data representations.

        :return: The object created from the DAO.
        :rtype: T
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


def to_dao(obj: Any, memo: Dict[int, Any] = None, keep_alive: Dict[int, Any] = None) -> DataAccessObject:
    """
    Convert any object to a dao class.

    :param obj: The object to convert to a dao.
    :param memo: A dictionary to keep track of already converted objects.
    :param keep_alive: A dictionary to keep the object alive during the conversion.
    """
    dao_class = get_dao_class(type(obj))
    if dao_class is None:
        raise NoDAOFoundError(type(obj))
    return dao_class.to_dao(obj, memo, keep_alive)
