from __future__ import annotations

from typing_extensions import Optional, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from .example_classes import Pose

@dataclass
class PoseAnnotation:
    name: str
    pose: Optional['Pose'] = field(default=None, repr=False, kw_only=True)
