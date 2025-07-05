import logging
import sys
import unittest
from dataclasses import fields

from sqlalchemy import create_engine
from sqlalchemy.orm import registry, Session, clear_mappers

import ormatic
from classes.cyclic_imports import PoseAnnotation
from classes.example_classes import Pose
from ormatic.field_info import FieldInfo
from ormatic.ormatic import ORMatic


class UnfinishedTypeTestCase(unittest.TestCase):

    def test_unfinished_type_field_info(self):
        f = [f for f in fields(PoseAnnotation) if f.name == "pose"][0]
        fi = FieldInfo(PoseAnnotation, f)


if __name__ == '__main__':
    unittest.main()
