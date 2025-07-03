import unittest

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import registry, Session

from classes.example_classes import PhysicalObject
from classes.orm_interface import *


class InterfaceTestCase(unittest.TestCase):

    session: Session
    engine: Engine

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine('sqlite:///:memory:')
        cls.session = Session(cls.engine)
        Base.metadata.create_all(cls.engine)

    def test_position(self):
        p1 = Position(1, 2, 3)

        p1dao = PositionDAO.to_dao(p1)
        print(p1dao.x, p1dao.y, p1dao.z)

        # self.session.add(o1)
        # self.session.add(p1)
        # self.session.commit()
        #
        # # test the content of the database
        # queried_p1 = self.session.scalars(select(Position)).one()
        # queried_o1 = self.session.scalars(select(Orientation)).one()
        # self.assertEqual(queried_p1, p1)
        # self.assertEqual(queried_o1, o1)


if __name__ == '__main__':
    unittest.main()
