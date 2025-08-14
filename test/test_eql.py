import unittest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, configure_mappers

from entity_query_language.entity import let, an, entity
from entity_query_language import Or, in_

from classes.example_classes import Position, Pose, Orientation
from classes.sqlalchemy_interface import Base, PositionDAO, PoseDAO, OrientationDAO

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

        results = eql_to_sql(query, self.session).evaluate()

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], PositionDAO)
        self.assertEqual(results[0].z, 4)

    def test_translate_or_condition(self):
        self.session.add(PositionDAO(x=1, y=2, z=3))
        self.session.add(PositionDAO(x=1, y=2, z=4))
        self.session.add(PositionDAO(x=2, y=9, z=10))
        self.session.commit()

        query = an(entity(position := let(Position, []), Or(position.z == 4, position.x == 2)), show_tree=False)

        result = eql_to_sql(query, self.session).evaluate()

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

        # Act
        result = eql_to_sql(query, self.session).evaluate()

        # Assert: only the pose with position.z == 4 should match
        rows = result
        self.assertEqual(len(rows), 1)
        self.assertIsInstance(rows[0], PoseDAO)
        self.assertIsNotNone(rows[0].position)
        self.assertEqual(rows[0].position.z, 4)
    #
    # def test_translate_in_operator(self):
    #     # Arrange
    #     self._add_positions([(1, 2, 3), (5, 2, 6), (7, 8, 9)])
    #
    #     # Build EQL expression: position.x in [1, 7]
    #     position = let(type_=Position, domain=[Position(0, 0, 0)])
    #     expr = in_(position.x, [1, 7])
    #
    #     # Act
    #     stmt = eql_to_sql(expr)
    #     rows = self.session.scalars(stmt).all()
    #
    #     # Assert: x in {1,7}
    #     xs = sorted([r.x for r in rows])
    #     self.assertEqual(xs, [1, 7])


if __name__ == '__main__':
    unittest.main()
