from typing import Type, get_args, Dict

from sqlalchemy.orm import MappedAsDataclass, registry
from typing_extensions import TypeVar, Generic, Self, Optional

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
        base = cls.__orig_bases__[0]
        type_args = get_args(base)
        if not type_args:
            raise TypeError(
                f"Cannot determine original class for {cls.__name__!r}. "
                "Did you forget to parameterise the DataAccessObject subclass?"
            )
        return type_args[0]

    @classmethod
    def from_original_class(cls, original_instance: T) -> Self:
        """
        Create an instance of this class from an instance of the original class.
        If a different specification than the specification of the original class is needed, overload this method.

        :return: An instance of this class created from the original class.
        """
        raise NotImplementedError()

    def to_original_class(self) -> T:
        """
        :return: An instance of this class created from the original class.
        """
        raise NotImplementedError()


class ORMatic2:
    """
    Class that takes in a bunch of classes and creates DAOs for them that allow database interaction.
    """
