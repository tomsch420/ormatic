from __future__ import annotations

import inspect
import datetime
import sys
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Type, List
from sqlalchemy import types



class classproperty:
    """
    A decorator that allows a class method to be accessed as a property.
    """

    def __init__(self, fget):
        self.fget = fget

    def __get__(self, instance, owner):
        return self.fget(owner)

def classes_of_module(module) -> List[Type]:
    """
    Get all classes of a given module.

    :param module: The module to inspect.
    :return: All classes of the given module.
    """

    result = []
    for name, obj in inspect.getmembers(sys.modules[module.__name__]):
        if inspect.isclass(obj) and obj.__module__ == module.__name__:
            result.append(obj)
    return result

def recursive_subclasses(cls):
    """
    :param cls: The class.
    :return: A list of the classes subclasses.
    """
    return cls.__subclasses__() + [g for s in cls.__subclasses__() for g in recursive_subclasses(s)]

leaf_types = (int, float, str, Enum, datetime.datetime, bool)