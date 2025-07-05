from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict

from sqlalchemy import types, TypeDecorator
from typing_extensions import List, Optional, Type

from ormatic.dao import DataAccessObject

# check that custom enums works
class Element(Enum):
    C = "c"
    H = "h"

# Check that Types attributes work
@dataclass
class PositionTypeWrapper:
    position_type: Type[Position]

# check that flat classes work
@dataclass
class Position:
    x: float
    y: float
    z: float

# check that classes with optional values work
@dataclass
class Orientation:
    x: float
    y: float
    z: float
    w: Optional[float]


# check that one to one relationship work
@dataclass
class Pose:
    position: Position
    orientation: Orientation


# check that one to many relationship to built in types and non built in types work
@dataclass
class Positions:
    positions: List[Position]
    some_strings: List[str]

# check that one to many relationships work where the many side is of the same type
@dataclass
class DoublePositionAggregator:
    positions1: List[Position]
    positions2: List[Position]

# check that inheritance works
@dataclass
class Position4D(Position):
    w: float

# # check that explicit mappings work
# @dataclass
# class PartialPosition(DataAccessObject[Position4D]):
#     x: float
#     y: float
#     z: float


# check with tree like classes
@dataclass
class Node:
    parent: Optional[Node] = None

class NotMappedParent:
    ...

# check that enum references work
@dataclass
class Atom(NotMappedParent):
    element: Element
    type: int
    charge: float


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


@dataclass
class OriginalSimulatedObject:
    concept: PhysicalObject
    placeholder: float = field(default=0)


@dataclass
class ObjectAnnotation:
    """
    Class for checking how classes that are explicitly mapped interact with original types.
    """
    object_reference: OriginalSimulatedObject

@dataclass
class KinematicChain:
    name: str

@dataclass
class Torso(KinematicChain):
    """
    A Torso is a kinematic chain connecting the base of the robot with a collection of other kinematic chains.
    """
    kinematic_chains: List[KinematicChain] = field(default_factory=list)
    """
    A collection of kinematic chains that are connected to the torso.
    """

@dataclass
class Parent:
    name: str

@dataclass
class ChildMapped(Parent):
    attribute1: int

@dataclass
class ChildNotMapped(Parent):
    attribute2: int
    unparseable: Dict[int, int]


@dataclass
class Entity:
    name: str


# Define a derived class
@dataclass
class DerivedEntity(Entity):
    description: str = "Default description"

#
# # Define an explicit mapping DAO that maps to the base entity class
# @dataclass
# class EntityDAO(DataAccessObject[Entity]):
#     name: str

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

        module_name, class_name = str(value).rsplit('.', 1)
        module = importlib.import_module(module_name)
        return getattr(module, class_name)()
