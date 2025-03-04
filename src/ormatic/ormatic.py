from __future__ import annotations

import typing
from dataclasses import dataclass, Field, fields
from functools import cached_property
from typing import Any

import sqlalchemy
from sqlalchemy import Table, Integer, ARRAY, Column
from sqlalchemy.orm import relationship, registry
from typing_extensions import List, Type, Dict, get_origin


class ParseError(TypeError):
    """
    Error that will be raised when the parser encounters something that can/should not be parsed.

    For instance, Union types
    """
    pass


def sqlalchemy_type(type: Type) -> Type[sqlalchemy.types.TypeEngine]:
    """
    Convert a Python type to a SQLAlchemy type.

    :param type: A Python type
    :return: The corresponding SQLAlchemy type
    """
    if type == int:
        return sqlalchemy.Integer
    elif type == float:
        return sqlalchemy.Float
    elif type == str:
        return sqlalchemy.String
    elif type == bool:
        return sqlalchemy.Boolean
    else:
        raise ValueError(f"Could not parse type {type}.")


def is_builtin_class(clazz: Type):
    """
    Check if a class is a builtin class.

    :param clazz: The class to check
    :return: True if the class is a builtin class, False otherwise
    """
    return clazz.__module__ == 'builtins'


def column_of_field(field: Field) -> sqlalchemy.Column:
    """
    Create a SQLAlchemy column from a dataclass field.

    :param field: The field to create a column from
    :return: The created column
    """
    return sqlalchemy.Column(field.name, sqlalchemy_type(field.type))


def is_iterable(clazz: Type) -> bool:
    """
    Check if a class is an iterable.

    :param clazz: The class to check
    :return: True if the class is an iterable, False otherwise
    """
    return get_origin(clazz) in [list, set, tuple]


class ORMatic:
    """
    ORMatic is a tool for generating SQLAlchemy ORM models from dataclasses.
    """

    mapper_registry: registry
    """
    The SQLAlchemy mapper registry. This is needed for the relationship configuration.
    """

    class_dict: Dict[Type, WrappedTable]
    """
    A dictionary mapping classes to their corresponding WrappedTable objects. This is used to gather all the columns and
    relationships between the classes before creating the SQL tables.
    """

    foreign_key_postfix = "_id"
    """
    The postfix that will be added to foreign key columns (not the relationships).
    """

    def __init__(self, classes: List[Type], mapper_registry: registry):
        self.class_dict = {}
        for clazz in classes:
            self.class_dict[clazz] = WrappedTable(clazz, [], {}, mapper_registry)
        self.mapper_registry = mapper_registry
        self.parse_classes()

    def make_all_tables(self) -> Dict[Type, Table]:
        """
        Create all the SQLAlchemy tables from the classes in the class_dict.

        :return: A dictionary mapping classes to their corresponding SQLAlchemy tables.
        """
        return {wrapped_table.clazz: wrapped_table.make_table for wrapped_table in self.class_dict.values()}

    def parse_classes(self):
        """
        Parse all the classes in the class_dict, aggregating the columns, primary keys, foreign keys and relationships.
        """
        for wrapped_table in self.class_dict.values():
            self.parse_class(wrapped_table)

    def parse_class(self, wrapped_table: WrappedTable):
        """
        Parse a single class.
        :param wrapped_table: The WrappedTable object to parse
        """
        for field in fields(wrapped_table.clazz):
            self.parse_field(wrapped_table, field)

    def parse_field(self, wrapped_table: WrappedTable, field: Field):
        """
        Parse a single field.
        :param wrapped_table: The WrappedTable object to parse
        :param field: The field to parse
        """
        print("=" * 80)
        print(field)
        if field.name.startswith("_"):
            print("private")
            return
        elif is_builtin_class(field.type):
            print("builtin type")
            wrapped_table.parse_builtin_type(field)
        elif field.type in self.class_dict:
            print("class type")
            self.create_one_to_one_relationship(wrapped_table, field)
        elif is_iterable(field.type):
            print("iterable")
            self.parse_iterable_field(wrapped_table, field)

    def create_one_to_one_relationship(self, wrapped_table: WrappedTable, field: Field):
        """
        Create a one-to-one relationship between two tables.
        The relationship is created using a ForeignKey column and a relationship property on `wrapped_table` and
         a relationship property on the `field.type` table. TODO Second part

        :param wrapped_table: The table that the relationship will be created on
        :param field: The field that the relationship will be created for
        """
        other_wrapped_table = self.class_dict[field.type]

        # create foreign key to field.type
        fk = sqlalchemy.Column(field.name + self.foreign_key_postfix, Integer,
                               sqlalchemy.ForeignKey(other_wrapped_table.full_primary_key_name), nullable=True)
        wrapped_table.columns.append(fk)

        wrapped_table.properties[field.name] = sqlalchemy.orm.relationship(other_wrapped_table.tablename)

    def parse_iterable_field(self, wrapped_table: WrappedTable, field: Field):
        """
        Parse an iterable field and create a one to many relationship if needed.
        :param wrapped_table: The table that the relationship will be created on
        :param field: The field to parse
        """
        inner_type = typing.get_args(field.type)[0]

        if is_builtin_class(inner_type):
            column = sqlalchemy.Column(field.name, ARRAY(sqlalchemy_type(inner_type)))
            wrapped_table.columns.append(column)

        elif inner_type in self.class_dict:
            self.create_one_to_many_relationship(wrapped_table, field, inner_type)

        else:
            raise ParseError(f"Could not parse iterable field {field}")

    def create_one_to_many_relationship(self, wrapped_table: WrappedTable, field: Field, inner_type: Type):
        """
        Create a one-to-many relationship between two tables.
        The relationship is created using a ForeignKey column in `inner_type` and a relationship property on both tables.
        TODO this is not working correctly yet.

        :param wrapped_table: The "one" side of the relationship.
        :param field: The "many" side of the relationship.
        :param inner_type: The type of the elements in the iterable
        """
        other_wrapped_table = self.class_dict[inner_type]

        # add a foreign key to the other table describing this table
        fk = sqlalchemy.Column(wrapped_table.foreign_key_name + self.foreign_key_postfix, Integer,
                               sqlalchemy.ForeignKey(
                                   f"{other_wrapped_table.tablename}.{other_wrapped_table.primary_key_name}"),
                               nullable=True)
        other_wrapped_table.columns.append(fk)

        # add a relationship to this table holding the list of objects from the field.type table
        wrapped_table.properties[field.name] = sqlalchemy.orm.relationship(inner_type,
                                                                           back_populates=wrapped_table.tablename)

        # add a relationship to the other table holding the object of this table
        other_wrapped_table.properties[wrapped_table.tablename] = sqlalchemy.orm.relationship(wrapped_table.clazz,
                                                                                              backref=other_wrapped_table.tablename)


@dataclass
class WrappedTable:
    """
    A class that wraps a dataclass and contains all the information needed to create a SQLAlchemy table from it.
    """

    clazz: Type
    """
    The dataclass that this WrappedTable wraps.
    """

    columns: List[Column]
    """
    A list of columns that will be added to the SQLAlchemy table.
    """

    properties: Dict[str, Any]
    """
    A dictionary of properties that will be added to the registry properties."""

    mapper_registry: registry
    """
    The SQLAlchemy mapper registry. This is needed for the relationship configuration.
    """

    primary_key_name: str = "id"
    """
    The name of the primary key column.
    """

    def __post_init__(self):
        pk_column = Column(self.primary_key_name,
                           sqlalchemy.Integer, primary_key=True, autoincrement=True)
        self.columns.append(pk_column)

    @property
    def tablename(self):
        return self.clazz.__name__

    @property
    def full_primary_key_name(self):
        return f"{self.tablename}.{self.primary_key_name}"

    @property
    def foreign_key_name(self):
        return self.tablename.lower()

    @cached_property
    def make_table(self):
        """
        :return: The SQLAlchemy table created from the dataclass. Call this after all columns and relationships have been
        added to the WrappedTable.
        """
        table = Table(
            self.tablename,
            self.mapper_registry.metadata,
            *self.columns, )
        self.mapper_registry.map_imperatively(self.clazz, table, properties=self.properties)
        return table

    def parse_builtin_type(self, field: Field):
        """
        Add a column for a field with a builtin type.
        :param field: The field to parse
        """
        self.columns.append(column_of_field(field))
