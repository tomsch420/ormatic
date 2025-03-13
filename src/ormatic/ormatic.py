from __future__ import annotations

from typing import TYPE_CHECKING, TextIO

import networkx as nx

import typing

from dataclasses import dataclass, Field, fields, field
from functools import cached_property
from typing import Any

import sqlacodegen.generators
import sqlalchemy
from sqlacodegen.utils import render_callable
from sqlalchemy import Table, Integer, ARRAY, Column, ForeignKey
from sqlalchemy.orm import relationship, registry, polymorphic_union, Mapper, Relationship
from sqlalchemy.orm.relationships import _RelationshipDeclared, RelationshipProperty
from typing_extensions import List, Type, Dict, get_origin, Optional
import logging

logger = logging.getLogger(__name__)


class ParseError(TypeError):
    """
    Error that will be raised when the parser encounters something that can/should not be parsed.

    For instance, Union types
    """
    pass


def sqlalchemy_type(type_: Type) -> Type[sqlalchemy.types.TypeEngine]:
    """
    Convert a Python type to a SQLAlchemy type.

    :param type_: A Python type
    :return: The corresponding SQLAlchemy type
    """
    if type_ == int:
        return sqlalchemy.Integer
    elif type_ == float:
        return sqlalchemy.Float
    elif type_ == str:
        return sqlalchemy.String
    elif type_ == bool:
        return sqlalchemy.Boolean
    else:
        raise ValueError(f"Could not parse type {type_}.")


def is_builtin_class(clazz: Type):
    """
    Check if a class is a builtin class.

    :param clazz: The class to check
    :return: True if the class is a builtin class, False otherwise
    """
    return clazz.__module__ == 'builtins' and not is_iterable(clazz)


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

    polymorphic_union: Dict[str, Table]
    """
    Dictionary that maps the polymorphic identifier to the table in inheritance structures.
    """

    inheritance_diagram: nx.DiGraph

    def __init__(self, classes: List[Type], mapper_registry: registry):
        self.class_dict = {}

        self.inheritance_diagram = nx.DiGraph()

        for clazz in classes:

            # get the inheritance tree
            bases = [base for base in clazz.__bases__ if base in classes]
            if len(bases) > 1:
                raise ParseError(f"Multiple inheritance is not supported. {clazz} has multiple mapped bases: {bases}")

            base = self.class_dict[bases[0]] if bases else None

            wrapped_table = WrappedTable(clazz, [], {}, mapper_registry, parent_class=base)

            self.class_dict[clazz] = wrapped_table
            self.inheritance_diagram.add_node(wrapped_table)

            # add the class to the subclasses of the base class
            if base:
                base.subclasses.append(wrapped_table)
                self.inheritance_diagram.add_edge(base, wrapped_table)

        self.mapper_registry = mapper_registry
        self.polymorphic_union = {}
        self.parse_classes()

    def make_all_tables(self) -> Dict[Type, Table]:
        """
        Create all the SQLAlchemy tables from the classes in the class_dict.

        :return: A dictionary mapping classes to their corresponding SQLAlchemy tables.
        """
        return {wrapped_table.clazz: wrapped_table.mapped_table for wrapped_table in self.class_dict.values()}

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

        # if this table is the root of a non-empty inheritance structure
        if wrapped_table.is_root_of_non_empty_inheritance_structure:
            # add a column for the polymorphic type to this table
            wrapped_table.columns.append(Column(wrapped_table.polymorphic_on_name, sqlalchemy.String))

        for field in fields(wrapped_table.clazz):
            self.parse_field(wrapped_table, field, skip_fields=(fields(wrapped_table.parent_class.clazz)
                                                                if wrapped_table.parent_class else []))

    def generate_polymorphic_union(self):
        for wrapped_table in self.class_dict.values():
            if wrapped_table.has_parent_classes:
                self.polymorphic_union[wrapped_table.tablename] = wrapped_table.mapped_table

        return polymorphic_union(self.polymorphic_union, "type")

    def parse_field(self, wrapped_table: WrappedTable, field: Field, skip_fields: List[Field]):
        """
        Parse a single field.
        :param wrapped_table: The WrappedTable object to parse
        :param field: The field to parse
        """

        # skip inherited fields
        if field in skip_fields:
            return

        if field.name.startswith("_"):
            logger.info(f"Skipping {wrapped_table.clazz.__name__}.{field.name} because it starts with an underscore.")
            return
        elif is_builtin_class(field.type):
            logger.info(f"Parsing {wrapped_table.clazz.__name__}.{field.name} of type {field.type} as builtin type.")
            wrapped_table.parse_builtin_type(field)
        elif field.type in self.class_dict:
            logger.info(f"Parsing {wrapped_table.clazz.__name__}.{field.name} of type {field.type} "
                        f"as one to one relationship. The foreign key is constructed on {wrapped_table.clazz.__name__}.")
            self.create_one_to_one_relationship(wrapped_table, field)
        elif is_iterable(field.type):
            logger.info(f"Parsing {wrapped_table.clazz.__name__}.{field.name} of type {field.type} "
                        f"as one to many relationship. The foreign key is constructed on {wrapped_table.clazz.__name__}.")
            self.parse_iterable_field(wrapped_table, field)

    def create_one_to_one_relationship(self, wrapped_table: WrappedTable, field: Field):
        """
        Create a one-to-one relationship between two tables.
        The relationship is created using a ForeignKey column and a relationship property on `wrapped_table` and
         a relationship property on the `field.type` table. TODO Second part or think if this is nescessary

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
        The relationship is created using a ForeignKey column in `inner_type` and a relationship property on both
        tables.

        :param wrapped_table: The "one" side of the relationship.
        :param field: The "many" side of the relationship.
        :param inner_type: The type of the elements in the iterable
        """
        child_wrapped_table = self.class_dict[inner_type]

        # add a foreign key to the other table describing this table
        fk = sqlalchemy.Column(wrapped_table.foreign_key_name + self.foreign_key_postfix, Integer,
                               sqlalchemy.ForeignKey(wrapped_table.full_primary_key_name),
                               nullable=True)
        child_wrapped_table.columns.append(fk)

        # add a relationship to this table holding the list of objects from the field.type table
        wrapped_table.properties[field.name] = sqlalchemy.orm.relationship(inner_type,
                                                                           # back_populates=wrapped_table.foreign_key_name,
                                                                           default_factory=get_origin(field.type))

    def to_python_file(self, generator: sqlacodegen.generators.TablesGenerator, file: TextIO):

        #write imports
        # collect imports
        imports = {clazz.__module__ for clazz in self.class_dict.keys()}
        for import_ in imports:
            file.write(f"import {import_}\n")

        file.write("from sqlalchemy.orm import registry, relationship \n")

        # write tables
        file.write(generator.generate())

        # add registry
        file.write("\n")
        file.write("mapper_registry = registry(metadata=metadata)\n")

        for wrapped_table in self.class_dict.values():
            file.write("\n")

            parsed_kwargs = wrapped_table.mapper_kwargs_for_python_file

            file.write(f"m_{wrapped_table.tablename} = mapper_registry."
                       f"map_imperatively({wrapped_table.clazz.__module__}.{wrapped_table.clazz.__name__}, "
                       f"t_{wrapped_table.tablename}, {parsed_kwargs})\n")



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

    polymorphic_on_name: str = "polymorphic_type"
    """
    The name of the column that will be used to identify polymorphic identities if any present.
    """

    polymorphic_union = None
    """
    The polymorphic union object that will be created if the class has subclasses.
    """

    subclasses: List[WrappedTable] = field(default_factory=list)
    """
    A list of subclasses as Wrapped Tables of the class that this WrappedTable wraps.
    """

    parent_class: Optional[WrappedTable] = None
    """
    The parent class of self.clazz if it exists.
    """

    @property
    def primary_key(self):
        if self.parent_class:
            column_type = ForeignKey(self.parent_class.full_primary_key_name)
        else:
            column_type = Integer

        return Column(self.primary_key_name, column_type, primary_key=True)

    @property
    def tablename(self):
        return self.clazz.__name__

    @property
    def full_primary_key_name(self):
        return f"{self.tablename}.{self.primary_key_name}"

    @property
    def foreign_key_name(self):
        return self.tablename.lower()

    @property
    def has_subclasses(self):
        return len(self.subclasses) > 0

    @property
    def is_root_of_non_empty_inheritance_structure(self):
        return self.has_subclasses and self.parent_class

    @property
    def mapper_kwargs(self):
        kwargs = {
            "properties": self.properties
        }

        if self.has_subclasses:
            kwargs["polymorphic_on"] = self.polymorphic_on_name
            kwargs["polymorphic_identity"] = self.tablename
        if self.parent_class:
            kwargs["polymorphic_identity"] = self.tablename
            kwargs["inherits"] = self.parent_class.mapped_table

        return kwargs

    @property
    def mapper_kwargs_for_python_file(self) -> str:
        result = {}
        properties = {}
        for name, relation in self.properties.items():
            relation: RelationshipProperty

            relation_argument = relation.argument

            if isinstance(relation.argument, type):
                relation_argument = relation.argument.__name__
                properties[name] = f"relationship(\"{relation_argument}\", default_factory=list)"
            else:
                properties[name] = f"relationship(\"{relation_argument}\")"

        if properties:
            result["properties"] = "dict(" + ", \n".join(f"{p}={v}" for p, v in properties.items()) + ")"

        if self.has_subclasses:
            result["polymorphic_on"] = f"\"{self.polymorphic_on_name}\""
            result["polymorphic_identity"] = f"\"{self.tablename}\""
        if self.parent_class:
            result["polymorphic_identity"] = f"\"{self.tablename}\""
            result["inherits"] = f"m_{self.parent_class.tablename}"

        result = ", ".join(f"{key} = {value}" for key, value in result.items())
        return result


    @cached_property
    def mapped_table(self) -> Mapper:
        """
        :return: The SQLAlchemy table created from the dataclass. Call this after all columns and relationships have been
        added to the WrappedTable.
        """

        columns = [self.primary_key] + self.columns
        if self.has_subclasses:
            columns.append(Column(self.polymorphic_on_name, sqlalchemy.String))

        table = Table(
            self.tablename,
            self.mapper_registry.metadata,
            *columns,
        )

        table = self.mapper_registry.map_imperatively(self.clazz, table, **self.mapper_kwargs)
        return table

    def parse_builtin_type(self, field: Field):
        """
        Add a column for a field with a builtin type.
        :param field: The field to parse
        """
        self.columns.append(column_of_field(field))

    def __hash__(self):
        return hash(self.clazz)
