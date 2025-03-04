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
class Poses:
    poses: List[Pose]
    some_strings: List[str]

