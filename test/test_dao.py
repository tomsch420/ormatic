import unittest
from dataclasses import dataclass

from ormatic.dao import DataAccessObject


@dataclass
class A:
    a: int

class ADAO(DataAccessObject[A]):
    ...


class DAOTestCase(unittest.TestCase):

    def test_dao(self):
        dao = ADAO()
        assert dao.original_class() == A


if __name__ == '__main__':
    unittest.main()
