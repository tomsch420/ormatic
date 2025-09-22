from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Sequence

from sqlalchemy import types, TypeDecorator
from typing_extensions import List, Optional, Type

from entity_query_language import symbol
from ormatic.dao import DataAccessObject, AlternativeMapping, T


# check that custom enums works
class Element(Enum):
    C = "c"
    H = "h"


# Check that Types attributes work
@symbol
@dataclass
class PositionTypeWrapper:
    position_type: Type[Position]


# check that flat classes work
@symbol
@dataclass
class Position:
    x: float
    y: float
    z: float


# check that classes with optional values work
@symbol
@dataclass
class Orientation:
    x: float
    y: float
    z: float
    w: Optional[float]


# check that one to one relationship work
@symbol
@dataclass
class Pose:
    position: Position
    orientation: Orientation


# check that one to many relationship to built in types and non built in types work
@symbol
@dataclass
class Positions:
    positions: List[Position]
    some_strings: List[str]


@symbol
@dataclass
class PositionsSubclassWithAnotherPosition(Positions):
    positions2: Position


# check that one to many relationships work where the many side is of the same type
@symbol
@dataclass
class DoublePositionAggregator:
    positions1: List[Position]
    positions2: List[Position]


# check that inheritance works
@symbol
@dataclass
class Position4D(Position):
    w: float


# check that inheriting from an inherited class works
@symbol
@dataclass
class Position5D(Position4D):
    v: float


# check with tree like classes
@symbol
@dataclass
class Node:
    parent: Optional[Node] = None


@symbol
class NotMappedParent: ...


# check that enum references work
@symbol
@dataclass
class Atom(NotMappedParent):
    element: Element
    type: int
    charge: float
    timestamp: datetime = field(default_factory=datetime.now)


# check that custom type checks work
class PhysicalObject:
    pass


class Cup(PhysicalObject):
    pass


class Bowl(PhysicalObject):
    pass


# @dataclass
# class MultipleInheritance(Position, Orientation):
#    pass


@symbol
@dataclass
class OriginalSimulatedObject:
    concept: PhysicalObject
    placeholder: float = field(default=0)


@symbol
@dataclass
class ObjectAnnotation:
    """
    Class for checking how classes that are explicitly mapped interact with original types.
    """

    object_reference: OriginalSimulatedObject


@symbol
@dataclass
class KinematicChain:
    name: str


@symbol
@dataclass
class Torso(KinematicChain):
    """
    A Torso is a kinematic chain connecting the base of the robot with a collection of other kinematic chains.
    """

    kinematic_chains: List[KinematicChain] = field(default_factory=list)
    """
    A collection of kinematic chains that are connected to the torso.
    """


@symbol
@dataclass
class Parent:
    name: str


@symbol
@dataclass
class ChildMapped(Parent):
    attribute1: int


@symbol
@dataclass
class ChildNotMapped(Parent):
    attribute2: int
    unparseable: Dict[int, int]


@symbol
@dataclass
class Entity:
    name: str
    attribute_that_shouldnt_appear_at_all: float = 0


# Define a derived class
@symbol
@dataclass
class DerivedEntity(Entity):
    description: str = "Default description"


@symbol
@dataclass
class EntityAssociation:
    """
    Class for checking how classes that are explicitly mapped interact with original types.
    """

    entity: Entity
    a: Sequence[str] = None


# Define an explicit mapping DAO that maps to the base entity class
@symbol
@dataclass
class CustomEntity(AlternativeMapping[Entity]):
    overwritten_name: str

    @classmethod
    def create_instance(cls, obj: Entity):
        result = cls(overwritten_name=obj.name)
        return result

    def create_from_dao(self) -> T:
        return Entity(name=self.overwritten_name)


class ConceptType(TypeDecorator):
    """
    Type that casts fields that are of type `type` to their class name on serialization and converts the name
    to the class itself through the globals on load.
    """

    impl = types.String(256)

    def process_bind_param(self, value: PhysicalObject, dialect):
        return value.__class__.__module__ + "." + value.__class__.__name__

    def process_result_value(self, value: impl, dialect) -> Optional[Type]:
        if value is None:
            return None

        module_name, class_name = str(value).rsplit(".", 1)
        module = importlib.import_module(module_name)
        return getattr(module, class_name)()


@symbol
@dataclass
class Reference:
    value: int = 0
    backreference: Optional[Backreference] = None


@symbol
@dataclass
class Backreference:
    unmappable: Dict[Any, int]
    reference: Reference = None


@symbol
@dataclass
class BackreferenceMapping(AlternativeMapping[Backreference]):
    values: List[int]
    reference: Reference

    @classmethod
    def create_instance(cls, obj: T):
        return cls(list(obj.unmappable.values()), obj.reference)

    def create_from_dao(self) -> T:
        return Backreference({v: v for v in self.values}, self.reference)


@symbol
@dataclass
class AlternativeMappingAggregator:
    entities1: List[Entity]
    entities2: List[Entity]


@symbol
@dataclass
class ItemWithBackreference:
    value: int = 0
    container: Container = None


@symbol
@dataclass
class Container:
    items: List[ItemWithBackreference]

    def __post_init__(self):
        for item in self.items:
            item.container = self


@symbol
@dataclass
class Vector:
    x: float


@symbol
@dataclass
class VectorMapped(AlternativeMapping[Vector]):
    x: float

    @classmethod
    def create_instance(cls, obj: T):
        return VectorMapped(obj.x)

    def create_from_dao(self) -> T:
        return Vector(self.x)


@symbol
@dataclass
class Rotation:
    angle: float


@symbol
@dataclass
class RotationMapped(AlternativeMapping[Rotation]):
    angle: float

    @classmethod
    def create_instance(cls, obj: T):
        return RotationMapped(obj.angle)


@symbol
@dataclass
class Transformation:
    vector: Vector
    rotation: Rotation


@symbol
@dataclass
class TransformationMapped(AlternativeMapping[Transformation]):
    vector: Vector
    rotation: Rotation

    @classmethod
    def create_instance(cls, obj: T):
        return TransformationMapped(obj.vector, obj.rotation)

    def create_from_dao(self) -> T:
        return Transformation(self.vector, self.rotation)


@symbol
@dataclass
class Shape:
    name: str
    origin: Transformation


@symbol
@dataclass
class Shapes:
    shapes: List[Shape]


@symbol
@dataclass
class MoreShapes:
    shapes: List[Shapes]


@symbol
@dataclass
class VectorsWithProperty:
    _vectors: List[Vector]

    @property
    def vectors(self) -> List[Vector]:
        return self._vectors


@symbol
@dataclass
class VectorsWithPropertyMapped(AlternativeMapping[VectorsWithProperty]):
    vectors: List[Vector]

    @classmethod
    def create_instance(cls, obj: T):
        return VectorsWithPropertyMapped(obj.vectors)

    def create_from_dao(self) -> T:
        return VectorsWithProperty(self.vectors)


@symbol
@dataclass
class ParentBase:
    name: str
    value: int


@symbol
@dataclass
class ChildBase(ParentBase):
    pass


@symbol
@dataclass
class ParentBaseMapping(AlternativeMapping[ParentBase]):
    name: str

    @classmethod
    def create_instance(cls, obj: T):
        if not isinstance(obj, Parent):
            raise TypeError(f"Expected Parent, got {type(obj)}")
        return ParentBaseMapping(obj.name)

    def create_from_dao(self) -> T:
        return ParentBase(self.name, 0)


@symbol
@dataclass
class ChildBaseMapping(ParentBaseMapping, AlternativeMapping[ChildBase]):

    @classmethod
    def create_instance(cls, obj: T):
        if not isinstance(obj, ChildMapped):
            raise TypeError(f"Expected TestClass2, got {type(obj)}")
        return ChildBaseMapping(obj.name)

    def create_from_dao(self) -> T:
        return ChildBase(self.name, 0)


@symbol
@dataclass
class PrivateDefaultFactory:
    public_value: int = 0
    _private_list: List[int] = field(default_factory=list)


@symbol
@dataclass
class Body:
    name: str


@symbol
@dataclass
class Handle(Body): ...


@symbol
@dataclass
class ContainerBody(Body): ...


@symbol
@dataclass
class Connection:
    parent: Body
    child: Body


@symbol
@dataclass
class Prismatic(Connection): ...


@symbol
@dataclass
class Fixed(Connection): ...


@symbol
@dataclass
class World:
    id_: int
    bodies: List[Body]
    connections: List[Connection] = field(default_factory=list)
