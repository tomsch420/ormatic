from dataclasses import dataclass


from typing_extensions import Union, Optional, List


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
    w: float

@dataclass
class Pose:
    position: Position
    orientation:  Orientation

@dataclass
class Positions:
    positions: List[Position]
    # some_strings: List[str] array are not postgresql only :(

class Position4D(Position):
    w: float

