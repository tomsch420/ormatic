from __future__ import annotations

from dataclasses import dataclass
from typing import Type
from sqlalchemy import types



class classproperty:
    """
    A decorator that allows a class method to be accessed as a property.
    """

    def __init__(self, fget):
        self.fget = fget

    def __get__(self, instance, owner):
        return self.fget(owner)


@dataclass
class ORMaticExplicitMapping:
    """
    Abstract class that is used to mark a class as an explicit mapping.
    """

    @classproperty
    def explicit_mapping(cls) -> Type:
        raise NotImplementedError
