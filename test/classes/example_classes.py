from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy import types
from typing_extensions import List, Optional, Type

from ormatic.utils import ORMaticExplicitMapping, classproperty


class Element(str, Enum):
    C = "c"
    H = "h"
    O = "o"
    N = "n"
    F = "f"
    B = "b"
    I = "i"

    def __repr__(self):
        return self.name


@dataclass
class PositionTypeWrapper:
    position_type: Type[Position]

@dataclass
class Position:
    x: float
    y: float
    z: float


@dataclass
class Orientation:
    x: float
    y: float
    z: float
    w: Optional[float]


@dataclass
class Pose:
    position: Position
    orientation: Orientation


@dataclass
class Positions:
    positions: List[Position]
    some_strings: List[str]

@dataclass
class DoublePositionAggregator:
    positions1: List[Position]
    positions2: List[Position]

@dataclass
class Position4D(Position):
    w: float


@dataclass
class PartialPosition(ORMaticExplicitMapping):
    x: float
    y: float
    z: float

    @classmethod
    @property
    def explicit_mapping(cls):
        return Position4D


@dataclass
class Position5D(Position):
    a: float


class ValueEnum(int, Enum):
    A = 1
    B = 2
    C = 3


@dataclass
class EnumContainer:
    value: ValueEnum


@dataclass
class Node:
    parent: Optional[Node] = None


@dataclass
class Atom:
    element: Element
    type: int
    charge: float


@dataclass
class Bond:
    atom1: Atom
    atom2: Atom
    type: int


@dataclass
class Molecule:
    ind1: int
    inda: int
    logp: float
    lumo: float
    mutagenic: bool

    atoms: List[Atom]
    bonds: List[Bond]

    @property
    def color(self):
        if [a for a in self.atoms if a.element == Element.I]:
            return "red"
        return "green"


class PhysicalObject:
    pass


class Cup(PhysicalObject):
    pass


class Bowl(PhysicalObject):
    pass

@dataclass
class OriginalSimulatedObject:
    concept: PhysicalObject
    pose: Pose
    placeholder: float


@dataclass
class SimulatedObject(ORMaticExplicitMapping):
    concept: PhysicalObject
    pose: Pose

    @classproperty
    def explicit_mapping(cls):
        return OriginalSimulatedObject


class PhysicalObjectType(types.TypeDecorator):
    """
    This type represents a physical object type.
    The database representation of this is a string while the in memory type is the instance of PhysicalObject.
    """
    cache_ok = True
    impl = types.String

    def process_bind_param(self, value, dialect):
        return value.__class__.__name__

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        cls = globals().get(value)
        if cls is not None and issubclass(cls, PhysicalObject):
            return cls()
        raise ValueError(f"Cannot map '{value}' to a PhysicalObject class.")

    def copy(self, **kw):
        return self.__class__(**kw)

