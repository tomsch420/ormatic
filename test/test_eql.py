import unittest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.orm import Session, configure_mappers

from entity_query_language.entity import let, an, entity, the
from entity_query_language import Or, in_

from classes.example_classes import Position, Pose, Orientation, Parent, World, Prismatic, Fixed, Body
from classes.sqlalchemy_interface import Base, PositionDAO, PoseDAO, OrientationDAO, ParentDAO, WorldDAO, FixedDAO, \
    PrismaticDAO
from ormatic.dao import to_dao

from ormatic.eql_interface import eql_to_sql
from ormatic.utils import drop_database


class EQLTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure SQLAlchemy mappings are configured
        configure_mappers()
        cls.engine = create_engine('sqlite:///:memory:')
        cls.session = Session(cls.engine)

    def setUp(self):
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        # Drop all tables to keep DB clean between tests
        drop_database(self.engine)

    @classmethod
    def tearDownClass(cls):
        cls.session.close()
        cls.engine.dispose()


    def test_translate_simple_greater(self):

        self.session.add(PositionDAO(x=1, y=2, z=3))
        self.session.add(PositionDAO(x=1, y=2, z=4))
        self.session.commit()

        query = an(entity(position := let(Position, []), position.z > 3), show_tree=False)

        translator = eql_to_sql(query, self.session)
        query_by_hand = select(PositionDAO).where(PositionDAO.z > 3)

        self.assertEqual(str(translator.sql_query), str(query_by_hand))

        results = translator.evaluate()

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], PositionDAO)
        self.assertEqual(results[0].z, 4)

    def test_translate_or_condition(self):
        self.session.add(PositionDAO(x=1, y=2, z=3))
        self.session.add(PositionDAO(x=1, y=2, z=4))
        self.session.add(PositionDAO(x=2, y=9, z=10))
        self.session.commit()

        query = an(entity(position := let(Position, []), Or(position.z == 4, position.x == 2)), show_tree=False)

        translator = eql_to_sql(query, self.session)

        query_by_hand = select(PositionDAO).where((PositionDAO.z == 4) | (PositionDAO.x == 2))
        self.assertEqual(str(translator.sql_query), str(query_by_hand))

        result = translator.evaluate()

        # Assert: rows with z==4 and x==2 should be returned (2 rows)
        zs = sorted([r.z for r in result])
        xs = sorted([r.x for r in result])
        self.assertEqual(len(result), 2)
        self.assertEqual(zs, [4, 10])
        self.assertEqual(xs, [1, 2])

    def test_translate_join_one_to_one(self):
        self.session.add(PoseDAO(position=PositionDAO(x=1, y=2, z=3),
                                 orientation=OrientationDAO(w=1.0, x=0.0, y=0.0, z=0.0)))
        self.session.add(PoseDAO(position=PositionDAO(x=1, y=2, z=4), orientation=OrientationDAO(w=1.0, x=0.0, y=0.0, z=0.0)))
        self.session.commit()

        query = an(entity(pose := let(Pose, []), pose.position.z > 3), show_tree=False)
        translator = eql_to_sql(query, self.session)
        query_by_hand = select(PoseDAO).join(PositionDAO).where(PositionDAO.z > 3)

        self.assertEqual(str(translator.sql_query), str(query_by_hand))

        result = translator.evaluate()

        # Assert: only the pose with position.z == 4 should match
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], PoseDAO)
        self.assertIsNotNone(result[0].position)
        self.assertEqual(result[0].position.z, 4)

    def test_translate_in_operator(self):
        self.session.add(PositionDAO(x=1, y=2, z=3))
        self.session.add(PositionDAO(x=5, y=2, z=6))
        self.session.add(PositionDAO(x=7, y=8, z=9))
        self.session.commit()


        query = an(entity(position := let(Position, []),
                          in_(position.x, [1, 7])), show_tree=False)

        # Act
        translator = eql_to_sql(query, self.session)

        query_by_hand = select(PositionDAO).where(PositionDAO.x.in_([1, 7]))
        self.assertEqual(str(translator.sql_query), str(query_by_hand))

        result = translator.evaluate()

        # Assert: x in {1,7}
        xs = sorted([r.x for r in result])
        self.assertEqual(xs, [1, 7])

    def test_the_quantifier(self):
        self.session.add(PositionDAO(x=1, y=2, z=3))
        self.session.add(PositionDAO(x=5, y=2, z=6))
        self.session.commit()

        query = the(entity(position := let(Position, []), position.y == 2), show_tree=False)
        translator = eql_to_sql(query, self.session)
        query_by_hand = select(PositionDAO).where(PositionDAO.y == 2)
        self.assertEqual(str(translator.sql_query), str(query_by_hand))

        with self.assertRaises(MultipleResultsFound):
            result = translator.evaluate()

    def test_equal(self):
        # Create the world with its bodies and connections
        world = World(1, [Body("Container1"), Body("Container2"), Body("Handle1"), Body("Handle2")])
        c1_c2 = Prismatic(world.bodies[0], world.bodies[1])
        c2_h2 = Fixed(world.bodies[1], world.bodies[3])
        world.connections = [c1_c2, c2_h2]

        dao = to_dao(world)
        self.session.add(dao)
        self.session.commit()

        # Query for the kinematic tree of the drawer which has more than one component.
        # Declare the placeholders
        prismatic_connection = let(type_=Prismatic, domain=world.connections)
        fixed_connection = let(type_=Fixed, domain=world.connections)

        # Write the query body
        result = an(entity(fixed_connection,
                               fixed_connection.parent == prismatic_connection.child)
                    )
        translator = eql_to_sql(result, self.session)

        query_by_hand = select(FixedDAO).join(PrismaticDAO, onclause=PrismaticDAO.child_id == FixedDAO.parent_id)
        self.assertEqual(str(translator.sql_query), str(query_by_hand))



if __name__ == '__main__':
    unittest.main()
