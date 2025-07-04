import logging
import os
import sys
import unittest

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
# Add the test directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, Column
from sqlalchemy.orm import registry, Session, clear_mappers

import ormatic
from classes import example_classes
from classes.example_classes import *
from ormatic.ormatic import ORMatic
from ormatic.utils import classes_of_module, recursive_subclasses


def is_data_column(column: Column):
    return not column.primary_key and len(column.foreign_keys) == 0 and column.name != "polymorphic_type"


class SQLAlchemyGenerationTestCase(unittest.TestCase):
    session: Session
    mapper_registry: registry
    ormatic_instance: ORMatic

    @classmethod
    def setUpClass(cls):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        ormatic.ormatic.logger.addHandler(handler)
        ormatic.ormatic.logger.setLevel(logging.DEBUG)

        cls.mapper_registry = registry()
        cls.engine = create_engine('sqlite:///:memory:')
        cls.session = Session(cls.engine)

        all_classes = set(classes_of_module(example_classes))
        all_classes -= set(recursive_subclasses(DataAccessObject))
        all_classes -= set(recursive_subclasses(Enum))
        all_classes -= {ChildNotMapped, PhysicalObject, Cup, Bowl, Torso}

        cls.ormatic_instance = ORMatic(list(all_classes), cls.mapper_registry)
        # cls.ormatic_instance.make_all_tables()

        # Generate SQLAlchemy declarative mappings
        with open(os.path.join(os.path.dirname(__file__), 'classes', 'sqlalchemy_interface.py'), 'w') as f:
            cls.ormatic_instance.to_sqlalchemy_file(f)

        clear_mappers()

    @classmethod
    def tearDownClass(cls):
        cls.mapper_registry.metadata.drop_all(cls.session.bind)
        clear_mappers()
        cls.session.close()

    def test_file_generation(self):
        # Check that the file was created
        file_path = os.path.join(os.path.dirname(__file__), 'classes', 'sqlalchemy_interface.py')
        self.assertTrue(os.path.exists(file_path))

        # Check file content
        with open(file_path, 'r') as f:
            content = f.read()

            # # Check for imports
            # self.assertIn("from sqlalchemy import Column", content)
            # self.assertIn("from sqlalchemy.ext.declarative import declarative_base", content)
            # self.assertIn("from sqlalchemy.orm import relationship", content)
            #
            # # Check for Base class declaration
            # self.assertIn("Base = declarative_base()", content)
            #
            # # Check for class definitions
            # self.assertIn("class PositionDAO(Base, DataAccessObject[Position]):", content)
            # self.assertIn("class OrientationDAO(Base, DataAccessObject[Orientation]):", content)
            #
            # # Check for table names
            # self.assertIn("__tablename__ = 'positiondao'", content)
            # self.assertIn("__tablename__ = 'orientationdao'", content)
            #
            # # Check for columns
            # self.assertIn("id = Column(Integer, primary_key=True)", content)
            # self.assertIn("x = Column(", content)
            # self.assertIn("y = Column(", content)
            # self.assertIn("z = Column(", content)


if __name__ == '__main__':
    unittest.main()
