import unittest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, configure_mappers

from entity_query_language.entity import let
from entity_query_language.symbolic import Or, in_

from classes.example_classes import Position
from classes.sqlalchemy_interface import Base, PositionDAO

from ormatic.eql_interface import eql_to_sqlalchemy
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

    def _add_positions(self, values):
        # values is a list of (x, y, z)
        for x, y, z in values:
            dao = PositionDAO.to_dao(Position(x, y, z))
            self.session.add(dao)
        self.session.commit()

    def test_translate_simple_greater(self):
        # Arrange
        self._add_positions([(1, 2, 3), (1, 2, 4)])

        # Build EQL expression: position.z > 3
        position = let(type_=Position, domain=[Position(0, 0, 0)])  # domain content is irrelevant for translation
        expr = position.z > 3

        # Act: translate to SQLAlchemy and execute
        stmt = eql_to_sqlalchemy(expr)
        rows = self.session.scalars(stmt).all()

        # Assert: only the row with z == 4 should match
        self.assertEqual(len(rows), 1)
        self.assertIsInstance(rows[0], PositionDAO)
        self.assertEqual(rows[0].z, 4)

    def test_translate_or_condition(self):
        # Arrange
        self._add_positions([(1, 2, 3), (1, 2, 4), (2, 9, 10)])

        # Build EQL expression: (z == 4) OR (x == 2)
        position = let(type_=Position, domain=[Position(0, 0, 0)])
        expr = Or(position.z == 4, position.x == 2)

        # Act
        stmt = eql_to_sqlalchemy(expr)
        rows = self.session.scalars(stmt).all()

        # Assert: rows with z==4 and x==2 should be returned (2 rows)
        zs = sorted([r.z for r in rows])
        xs = sorted([r.x for r in rows])
        self.assertEqual(len(rows), 2)
        self.assertEqual(zs, [4, 10])
        self.assertEqual(xs, [1, 2])

    def test_translate_in_operator(self):
        # Arrange
        self._add_positions([(1, 2, 3), (5, 2, 6), (7, 8, 9)])

        # Build EQL expression: position.x in [1, 7]
        position = let(type_=Position, domain=[Position(0, 0, 0)])
        expr = in_(position.x, [1, 7])

        # Act
        stmt = eql_to_sqlalchemy(expr)
        rows = self.session.scalars(stmt).all()

        # Assert: x in {1,7}
        xs = sorted([r.x for r in rows])
        self.assertEqual(xs, [1, 7])


if __name__ == '__main__':
    unittest.main()
