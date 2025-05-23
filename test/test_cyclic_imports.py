import unittest
import logging
import sys
import unittest
from dataclasses import fields

import sqlacodegen.generators
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import registry, Session, clear_mappers

import ormatic
from classes.cyclic_imports import PoseAnnotation
from classes.example_classes import Pose
from ormatic.field_info import FieldInfo
from ormatic.ormatic import ORMatic



@unittest.skip("Forward referenced types are not supported yet.")
class UnfinishedTypeTestCase(unittest.TestCase):
    session: Session
    mapper_registry: registry

    def setUp(self):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        ormatic.ormatic.logger.addHandler(handler)
        ormatic.ormatic.logger.setLevel(logging.INFO)

        self.mapper_registry = registry()
        engine = create_engine('sqlite:///:memory:')
        self.session = Session(engine)

    def tearDown(self):
        self.mapper_registry.metadata.drop_all(self.session.bind)
        clear_mappers()
        self.session.close()

    def test_unfinished_type_field_info(self):
        f = [f for f in fields(PoseAnnotation) if f.name == "pose"][0]
        fi = FieldInfo(PoseAnnotation, f)


if __name__ == '__main__':
    unittest.main()
