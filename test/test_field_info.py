import unittest
from dataclasses import fields

from ormatic.ormatic import FieldInfo
from classes.example_classes import *


def get_field_by_name(cls, name):
    for f in fields(cls):
        if f.name == name:
            return f


class FieldInfoTestCase(unittest.TestCase):

    def test_builtin_not_optional(self):
        f = get_field_by_name(Position, "x")
        field_info = FieldInfo(Position, f)

        self.assertEqual(field_info.optional, False)
        self.assertIsNone(field_info.container)
        self.assertEqual(field_info.type, float)
        self.assertTrue(field_info.is_builtin_class)

    def test_builtin_optional(self):
        f = get_field_by_name(Orientation, "w")
        field_info = FieldInfo(Orientation, f)

        self.assertEqual(field_info.optional, True)
        self.assertIsNone(field_info.container)
        self.assertEqual(field_info.type, float)
        self.assertTrue(field_info.is_builtin_class)

    def test_one_to_one_relationship(self):
        f = get_field_by_name(Pose, "position")
        field_info = FieldInfo(Pose, f)

        self.assertEqual(field_info.optional, False)
        self.assertEqual(field_info.container, None)
        self.assertEqual(field_info.type, Position)
        self.assertFalse(field_info.is_builtin_class)

    def test_one_to_many_relationship(self):
        f = get_field_by_name(Positions, "positions")

        field_info = FieldInfo(Positions, f)

        self.assertEqual(field_info.optional, False)
        self.assertEqual(field_info.container, list)
        self.assertEqual(field_info.type, Position)
        self.assertFalse(field_info.is_builtin_class)
