import logging
import os
import sys
import unittest

from sqlalchemy.orm import registry, Session

import ormatic
from classes import example_classes
from classes.example_classes import *
from ormatic.ormatic import ORMatic
from ormatic.utils import classes_of_module, recursive_subclasses


class SQLAlchemyGenerationTestCase(unittest.TestCase):
    session: Session
    mapper_registry: registry
    ormatic_instance: ORMatic

    @classmethod
    def setUpClass(cls):
        # Logger configuration is now handled in ormatic/__init__.py
        # Note: Default log level is INFO, was DEBUG here

        all_classes = set(classes_of_module(example_classes))
        all_classes -= set(recursive_subclasses(DataAccessObject))
        all_classes -= set(recursive_subclasses(Enum))
        all_classes -= {ChildNotMapped, PhysicalObject, Cup, Bowl, Torso}
        all_classes = {Position, Position4D, Atom, Orientation, Pose, Positions, DoublePositionAggregator,
                       PositionTypeWrapper, Parent, ChildMapped, Node, DerivedEntity, KinematicChain, Torso,
                       OriginalSimulatedObject, CustomEntity, EntityAssociation}

        cls.ormatic_instance = ORMatic(list(sorted(all_classes, key=lambda c: c.__name__)),
                                       {PhysicalObject: ConceptType, })

        # Generate SQLAlchemy declarative mappings
        with open(os.path.join(os.path.dirname(__file__), 'classes', 'sqlalchemy_interface.py'), 'w') as f:
            cls.ormatic_instance.to_sqlalchemy_file(f)

    def test_file_generation(self):
        # Check that the file was created
        file_path = os.path.join(os.path.dirname(__file__), 'classes', 'sqlalchemy_interface.py')
        self.assertTrue(os.path.exists(file_path))


if __name__ == '__main__':
    unittest.main()
