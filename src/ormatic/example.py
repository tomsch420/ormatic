from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from typing_extensions import List, Optional

from ormatic.ormatic import ORMaticExplicitMapping


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
    # some_strings: List[str] array are postgresql only :(


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
