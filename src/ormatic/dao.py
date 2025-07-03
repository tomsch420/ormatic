import inspect
from dataclasses import fields, is_dataclass
from typing_extensions import Type, get_args, Dict, Any, Self, TypeVar, Generic

T = TypeVar('T')
_DAO = TypeVar("_DAO", bound="DataAccessObject")



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
    def to_dao(cls, obj: T, memo: Dict[int, Any] = None) -> _DAO:
        """
        Create an instance of this class from an instance of the original class.
        If a different specification than the specification of the original class is needed, overload this method.

        :return: An instance of this class created from the original class.
        """

        if memo is None:
            memo = {}
        if id(obj) in memo:
            return memo[id(obj)]

    def from_dao(self, memo: Dict[int, Any] = None) -> T:
        """
        :return: An instance of this class created from the original class.
        """

        if memo is None:
            memo = {}
        if id(self) in memo:
            return memo[id(self)]


# inheritance
# foreign keys
# something like ORMexplcitmapping
# insert die das og objekt reinimmt
# get from database die das og objekt rausgibt
