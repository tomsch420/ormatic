import logging
import sys
import unittest

import sqlacodegen.generators
from sqlalchemy import Table, MetaData, Column, Integer, Float, create_engine, select
from sqlalchemy.orm import registry, Session, clear_mappers

import ormatic.example
from ormatic.example import *
from ormatic.ormatic import ORMatic


class DependencyGraphTestCase(unittest.TestCase):
    session: Session
    mapper_registry: registry

    def setUp(self):
        self.mapper_registry = registry()
        engine = create_engine('sqlite:///:memory:')
        self.session = Session(engine)

    def tearDown(self):
        self.mapper_registry.metadata.drop_all(self.session.bind)
        clear_mappers()
        self.session.close()

    def test_position(self):
        mapper_registry = registry()
        metadata_obj = MetaData()
        position_table = Table(
            'position', metadata_obj,
            Column('id', Integer, primary_key=True),
            Column('x', Float),
            Column('y', Float),
            Column('z', Float),
        )

        mapper_registry.map_imperatively(Position, position_table)

        p = Position(x=1, y=2, z=3)

        engine = create_engine('sqlite:///:memory:')
        metadata_obj.create_all(engine)
        session = Session(engine)
        session.add(p)
        # session.commit()

        result = session.scalars(select(Position)).first()


class ORMaticTestCase(unittest.TestCase):
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

    def test_no_dependencies(self):
        classes = [Position, Orientation]
        result = ORMatic(classes, self.mapper_registry)

        self.assertEqual(len(result.class_dict), 2)
        position_table = result.class_dict[Position].mapped_table
        orientation_table = result.class_dict[Orientation].mapped_table

        self.assertEqual(len(position_table.columns), 4)
        self.assertEqual(len(orientation_table.columns), 5)

        p1 = Position(x=1, y=2, z=3)
        o1 = Orientation(x=1, y=2, z=3, w=1)

        # create all tables
        self.mapper_registry.metadata.create_all(self.session.bind)
        self.session.add(o1)
        self.session.add(p1)
        self.session.commit()

        # test the content of the database
        queried_p1 = self.session.scalars(select(Position)).one()
        queried_o1 = self.session.scalars(select(Orientation)).one()
        self.assertEqual(queried_p1, p1)
        self.assertEqual(queried_o1, o1)

    def test_one_to_one_relationships(self):
        classes = [Position, Orientation, Pose]
        result = ORMatic(classes, self.mapper_registry)
        all_tables = result.make_all_tables()
        pose_table = result.class_dict[Pose].mapped_table.local_table

        # get foreign keys of pose_table
        foreign_keys = pose_table.foreign_keys
        self.assertEqual(len(foreign_keys), 2)

        p1 = Position(x=1, y=2, z=3)
        o1 = Orientation(x=1, y=2, z=3, w=1)
        pose1 = Pose(p1, o1)

        # create all tables
        self.mapper_registry.metadata.create_all(self.session.bind)
        self.session.add(pose1)
        self.session.commit()

        # test the content of the database
        queried_p1 = self.session.scalars(select(Position)).one()
        queried_o1 = self.session.scalars(select(Orientation)).one()
        queried_pose1 = self.session.scalars(select(Pose)).one()
        self.assertEqual(queried_p1, p1)
        self.assertEqual(queried_o1, o1)
        self.assertEqual(queried_pose1, pose1)

    def test_one_to_many(self):
        classes = [Position, Positions]
        result = ORMatic(classes, self.mapper_registry)
        result.make_all_tables()

        positions_table = result.class_dict[Positions].mapped_table.local_table
        position_table = result.class_dict[Position].mapped_table.local_table

        foreign_keys = position_table.foreign_keys
        self.assertEqual(len(foreign_keys), 1)

        self.assertEqual(len(positions_table.columns), 1)

        self.mapper_registry.metadata.create_all(self.session.bind)

        p1 = Position(x=1, y=2, z=3)
        p2 = Position(x=2, y=3, z=4)

        positions = Positions([p1, p2])

        self.session.add(positions)
        self.session.commit()

        positions = self.session.scalars(select(Positions)).one()
        self.assertEqual(positions.positions, [p1, p2])

    def test_inheritance(self):
        classes = [Position, Position4D]
        result = ORMatic(classes, self.mapper_registry)
        result.make_all_tables()

        position4d_table = result.class_dict[Position4D].mapped_table.local_table

        foreign_keys = position4d_table.foreign_keys
        self.assertEqual(len(foreign_keys), 1)
        self.assertEqual(len(position4d_table.columns), 2)

        # assert position table polymorphic identity
        self.mapper_registry.metadata.create_all(self.session.bind)

        p1 = Position(x=1, y=2, z=3)
        p2 = Position4D(x=2, y=3, z=4, w=2)

        self.session.add_all([p1, p2])
        self.session.commit()

        queried_p1 = self.session.scalars(select(Position)).all()
        self.assertEqual(queried_p1, [p1, p2])
        queried_p2 = self.session.scalars(select(Position4D)).first()
        self.assertIsInstance(queried_p2, Position)


    def test_all_together(self):
        classes = [Position, Orientation, Pose, Position4D, Positions]
        result = ORMatic(classes, self.mapper_registry)
        result.make_all_tables()
        self.mapper_registry.metadata.create_all(self.session.bind)

    def test_to_python_file(self):
        classes = [Position, Orientation, Pose, Position4D, Positions]
        ormatic = ORMatic(classes, self.mapper_registry)
        ormatic.make_all_tables()
        self.mapper_registry.metadata.create_all(self.session.bind)

        generator = sqlacodegen.generators.TablesGenerator(self.mapper_registry.metadata, self.session.bind, [])

        with open('orm_interface.py', 'w') as f:
            ormatic.to_python_file(generator, f)

if __name__ == '__main__':
    unittest.main()
