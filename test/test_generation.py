import logging
import sys
import unittest

import sqlacodegen.generators
from sqlalchemy import create_engine, select, text, Column
from sqlalchemy.orm import registry, Session, clear_mappers

import ormatic
from classes import example_classes
from classes.example_classes import *
from ormatic.ormatic import ORMatic
from ormatic.utils import classes_of_module, recursive_subclasses
import os


def is_data_column(column: Column):
    return not column.primary_key and len(column.foreign_keys) == 0 and column.name != "polymorphic_type"


class ORMaticTestCase(unittest.TestCase):
    session: Session
    mapper_registry: registry
    ormatic_instance: ORMatic


    @classmethod
    def setUpClass(cls):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        ormatic.ormatic.logger.addHandler(handler)
        ormatic.ormatic.logger.setLevel(logging.INFO)

        cls.mapper_registry = registry()
        cls.engine = create_engine('sqlite:///:memory:')
        cls.session = Session(cls.engine)

        all_classes = set(classes_of_module(example_classes))
        all_classes -= set(recursive_subclasses(DataAccessObject))
        all_classes -= set(recursive_subclasses(Enum))
        all_classes -= {ChildNotMapped, PhysicalObject, Cup, Bowl}

        cls.ormatic_instance = ORMatic(list(all_classes), cls.mapper_registry)
        cls.ormatic_instance.make_all_tables()

        generator = sqlacodegen.generators.DeclarativeGenerator(cls.mapper_registry.metadata, cls.session.bind, [])
        with open(os.path.join(os.path.dirname(__file__), 'classes','orm_interface.py'), 'w') as f:
            cls.ormatic_instance.to_python_file(generator, f)

        clear_mappers()

    @classmethod
    def tearDownClass(cls):
        cls.mapper_registry.metadata.drop_all(cls.session.bind)
        clear_mappers()
        cls.session.close()

    def test_no_dependencies(self):
        position_table = self.ormatic_instance.class_dict[Position].mapped_table
        orientation_table = self.ormatic_instance.class_dict[Orientation].mapped_table

        position_table_data = [c for c in position_table.columns if is_data_column(c)]
        self.assertEqual(len(position_table_data), 3)

        orientation_table_data = [c for c in orientation_table.columns if is_data_column(c)]
        self.assertEqual(len(orientation_table_data), 4)

        orientation_colum = [c for c in orientation_table.columns if c.name == 'w'][0]
        self.assertTrue(orientation_colum.nullable)

    def test_primary_keys(self):
        node_table = self.ormatic_instance.class_dict[Node].mapped_table
        primary_keys = [c for c in node_table.columns if c.primary_key]

        self.assertEqual(len(node_table.columns), 2)
        self.assertEqual(len(primary_keys), 1)

    def test_foreign_keys(self):
        og_sim_object_table = self.ormatic_instance.class_dict[ObjectAnnotation].mapped_table.local_table
        foreign_keys = og_sim_object_table.foreign_keys

        self.assertEqual(len(og_sim_object_table.columns), 2)
        self.assertEqual(len(foreign_keys), 1)


if __name__ == '__main__':
    unittest.main()
