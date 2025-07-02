import unittest
import os
import tempfile
from dataclasses import dataclass
from typing_extensions import Self

from sqlalchemy.orm import registry

from ormatic.dao import DataAccessObject, ORMatic2, T


@dataclass
class A:
    a: int


class ADAO(DataAccessObject[A]):
    ...


@dataclass
class Person:
    name: str
    age: int


@dataclass
class Product:
    name: str
    price: int
    description: str


class DAOTestCase(unittest.TestCase):

    def test_dao(self):
        dao = ADAO()
        assert dao.original_class() == A

    def test_ormatic2_creation(self):
        # Test creating ORMatic2 with classes
        ormatic = ORMatic2([Person, Product])

        # Check that DAO classes were created
        self.assertIn(Person, ormatic.dao_classes)
        self.assertIn(Product, ormatic.dao_classes)

        # Check DAO class names
        person_dao = ormatic.get_dao_class(Person)
        product_dao = ormatic.get_dao_class(Product)

        self.assertEqual(person_dao.__name__, "PersonDAO")
        self.assertEqual(product_dao.__name__, "ProductDAO")

    def test_dao_conversion(self):
        # Create ORMatic2 instance
        ormatic = ORMatic2([Person])
        person_dao_class = ormatic.get_dao_class(Person)

        # Create original instance
        original_person = Person(name="John", age=30)

        # Convert to DAO instance
        dao_person = person_dao_class.from_original_class(original_person)

        # Check field values were copied
        self.assertEqual(dao_person.name, "John")
        self.assertEqual(dao_person.age, 30)

        # Convert back to original
        converted_person = dao_person.to_original_class()

        # Check it's the right type and has the right values
        self.assertIsInstance(converted_person, Person)
        self.assertEqual(converted_person.name, "John")
        self.assertEqual(converted_person.age, 30)

    def test_to_python_file(self):
        # Create ORMatic2 instance
        ormatic = ORMatic2([Person, Product])
        p1  = Person(name="John", age=30)


        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as temp_file:
            file_path = temp_file.name
            print(file_path)

        try:
            # Write to file
            ormatic.to_python_file(file_path)

            # Check file exists
            self.assertTrue(os.path.exists(file_path))

            # Check file content
            with open(file_path, 'r') as f:
                content = f.read()

                # Check imports
                self.assertIn("from ormatic.dao import DataAccessObject", content)
                self.assertIn("from sqlalchemy.orm import MappedAsDataclass, DeclarativeBase, registry, mapped_column", content)

                # Check class definitions
                self.assertIn("class PersonDAO(Base, MappedAsDataclass, DataAccessObject[Person]):", content)
                self.assertIn("class ProductDAO(Base, MappedAsDataclass, DataAccessObject[Product]):", content)

                # Check fields
                self.assertIn("name: str = mapped_column", content)
                self.assertIn("age: int = mapped_column", content)
                self.assertIn("price: int = mapped_column", content)

        finally:
            ...
            # Clean up
            # if os.path.exists(file_path):
            #     os.remove(file_path)


if __name__ == '__main__':
    unittest.main()
