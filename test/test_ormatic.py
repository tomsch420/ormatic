import logging
import sys
import unittest

import sqlacodegen.generators
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import registry, Session, clear_mappers

import ormatic
from ormatic.ormatic import ORMatic
from classes.example_classes import *


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

        orientation_colum = [c for c in orientation_table.columns if c.name == 'w'][0]
        self.assertTrue(orientation_colum.nullable)

        p1 = Position(x=1, y=2, z=3)
        o1 = Orientation(x=1, y=2, z=3, w=None)

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

    def test_enum_parse(self):
        classes = [EnumContainer]
        result = ORMatic(classes, self.mapper_registry)
        result.make_all_tables()

        enum_container_table = result.class_dict[EnumContainer].mapped_table.local_table

        self.assertEqual(len(enum_container_table.columns), 2)
        self.assertEqual(len(enum_container_table.foreign_keys), 0)

        self.mapper_registry.metadata.create_all(self.session.bind)

        enum_container = EnumContainer(value=ValueEnum.A)
        self.session.add(enum_container)
        self.session.commit()

        queried_enum_container = self.session.scalars(select(EnumContainer)).one()
        self.assertEqual(queried_enum_container, enum_container)

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

        self.assertEqual(len(positions_table.columns), 2)

        self.mapper_registry.metadata.create_all(self.session.bind)

        p1 = Position(x=1, y=2, z=3)
        p2 = Position(x=2, y=3, z=4)

        positions = Positions([p1, p2], ["a", "b"])

        self.session.add(positions)
        self.session.commit()

        positions = self.session.scalars(select(Positions)).one()
        self.assertEqual(positions.positions, [p1, p2])

    def test_one_to_many_multiple(self):
        classes = [Position, DoublePositionAggregator]
        result = ORMatic(classes, self.mapper_registry)

        double_positions_table = result.class_dict[DoublePositionAggregator].mapped_table.local_table
        position_table = result.class_dict[Position].mapped_table.local_table

        foreign_keys = position_table.foreign_keys
        self.assertEqual(len(foreign_keys), 2)

        self.assertEqual(len(double_positions_table.columns), 1)

        self.mapper_registry.metadata.create_all(self.session.bind)

        p1 = Position(x=1, y=2, z=3)
        p2 = Position(x=2, y=3, z=4)
        p3 = Position(x=3, y=4, z=5)

        positions = DoublePositionAggregator([p1, p2], [p3])


        self.session.add(positions)
        self.session.commit()

        queried = self.session.scalars(select(DoublePositionAggregator)).one()
        self.assertEqual(positions, queried)


    def test_inheritance(self):
        classes = [Position, Position4D, Position5D]
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

    def test_tree_structure(self):
        classes = [Node]
        result = ORMatic(classes, self.mapper_registry)
        result.make_all_tables()

        self.mapper_registry.metadata.create_all(self.session.bind)

        n1 = Node()
        n2 = Node(parent=n1)
        n3 = Node(parent=n1)

        self.session.add_all([n1, n2, n3])
        self.session.commit()

        results = self.session.scalars(select(Node)).all()
        n1, n2, n3 = results
        self.assertIsNone(n1.parent)
        self.assertEqual(n2.parent, n1)
        self.assertEqual(n3.parent, n1)

    def test_all_together(self):
        classes = [Position, Orientation, Pose, Position4D, Positions, EnumContainer]
        result = ORMatic(classes, self.mapper_registry)
        result.make_all_tables()
        self.mapper_registry.metadata.create_all(self.session.bind)

    def test_to_python_file(self):
        classes = [Position, Orientation, Pose, Position4D, Positions, EnumContainer, Node, SimulatedObject, DoublePositionAggregator]
        ormatic = ORMatic(classes, self.mapper_registry, {PhysicalObject: PhysicalObjectType()})
        ormatic.make_all_tables()
        self.mapper_registry.metadata.create_all(self.session.bind)

        generator = sqlacodegen.generators.TablesGenerator(self.mapper_registry.metadata, self.session.bind, [])

        with open('orm_interface.py', 'w') as f:
            ormatic.to_python_file(generator, f)

        # with open('orm_interface.py', 'r') as f:
        #     exec(f.read())

    def test_molecule(self):
        classes = [Atom, Bond, Molecule]
        ormatic = ORMatic(classes, self.mapper_registry)
        ormatic.make_all_tables()
        self.mapper_registry.metadata.create_all(self.session.bind)

        atom = Atom(Element.I, 1, 1.0)
        bond = Bond(atom, atom, 1)
        molecule = Molecule(1, 1, 1.0, 1.0, True, [atom], [bond])
        self.session.add_all([atom, bond, molecule])
        self.session.commit()

        result = self.session.scalars(select(Molecule).join(Atom).where(Atom.element == Element.I).distinct()).first()
        self.assertEqual(result, molecule)
        self.assertEqual(result.color, 'red')

    def test_explicit_mappings(self):
        classes = [PartialPosition]
        ormatic = ORMatic(classes, self.mapper_registry)
        ormatic.make_all_tables()
        self.mapper_registry.metadata.create_all(self.session.bind)

        p1 = Position4D(x=1, y=2, z=0, w=0)
        p2 = Position4D(x=2, y=3, z=0, w=0)
        self.session.add_all([p1, p2])
        self.session.commit()

        result = self.session.scalars(select(Position4D)).all()
        self.assertEqual(len(result), len([p1, p2]))
        self.assertEqual(result, [p1, p2])

    def test_type_casting(self):
        classes = [Position, Orientation, Pose, SimulatedObject]
        ormatic = ORMatic(classes, self.mapper_registry, type_mappings={PhysicalObject: PhysicalObjectType()})
        ormatic.make_all_tables()

        self.mapper_registry.metadata.create_all(self.session.bind)

        obj1 = OriginalSimulatedObject(Bowl(), Pose(Position(0,0,0), Orientation(0,0,0,1)), 5)
        self.session.add(obj1)
        self.session.commit()
        result = self.session.scalar(select(OriginalSimulatedObject))

        self.assertEqual(result, obj1)
        self.assertIsInstance(result.concept, Bowl)
        self.assertEqual(result.concept, obj1.concept)
        self.assertEqual(result.concept, obj1.concept)

        with self.session.bind.connect() as connection:
            result = connection.execute(text("select * from SimulatedObject JOIN Pose ON SimulatedObject.pose_id = Pose.id"))
            store_rows = []
            for row in result:
                store_rows.append(row)

        self.assertEqual(len(store_rows[0]), 6)
        self.assertEqual(type(store_rows[0][1]), str)

    def test_type_type(self):
        classes = [PositionTypeWrapper]
        ormatic = ORMatic(classes, self.mapper_registry)
        ormatic.make_all_tables()
        self.mapper_registry.metadata.create_all(self.session.bind)

        wrapper = PositionTypeWrapper(Position)
        self.session.add(wrapper)
        self.session.commit()
        result = self.session.scalars(select(PositionTypeWrapper)).one()
        self.assertEqual(result, wrapper)



if __name__ == '__main__':
    unittest.main()
