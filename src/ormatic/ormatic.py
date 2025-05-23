from __future__ import annotations

import logging
from dataclasses import dataclass, Field, fields, field
from functools import cached_property
from typing import Any
from typing import TextIO

import networkx as nx
import sqlacodegen.generators
import sqlalchemy
from sqlalchemy import Table, Integer, Column, ForeignKey, JSON
from sqlalchemy.orm import relationship, registry, Mapper
from typing_extensions import List, Type, Dict, Optional

from .custom_types import TypeType
from .field_info import ParseError, FieldInfo, RelationshipInfo, CustomTypeInfo
from .utils import ORMaticExplicitMapping

logger = logging.getLogger(__name__)


class ORMatic:
    """
    ORMatic is a tool for generating SQLAlchemy ORM models from a set of dataclasses.
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

    class_dependency_graph: Optional[nx.DiGraph] = None
    """
    A direct acyclic graph containing the class hierarchy.
    """

    def __init__(self, classes: List[Type], mapper_registry: registry, type_mappings: Dict[Type, Any] = None):
        """
        :param classes: The list of classes to be mapped.
        :param mapper_registry: The SQLAlchemy mapper registry. This is needed for the relationship configuration.
        """

        #  initialize the instance variables
        self.type_mappings = type_mappings or {}
        self.mapper_registry = mapper_registry
        self.polymorphic_union = {}
        self.class_dict = {}

        # create the class dependency graph
        self.make_class_dependency_graph(classes)

        # create the classes in dependency-resolved order
        for clazz in nx.topological_sort(self.class_dependency_graph):

            # get the inheritance tree
            bases: List[Type] = [base for (base, _) in self.class_dependency_graph.in_edges(clazz)]
            if len(bases) > 1:
                raise ParseError(f"Multiple inheritance is not supported. {clazz} has multiple mapped bases: {bases}")

            base = self.class_dict[bases[0]] if bases else None

            # wrap the classes to aggregate the needed properties before compiling it with sql
            wrapped_table = WrappedTable(clazz=clazz, mapper_registry=mapper_registry, parent_class=base)

            self.class_dict[clazz] = wrapped_table

            # add the class to the subclasses of the base class
            if base:
                base.subclasses.append(wrapped_table)

        # parse all classes
        self.parse_classes()

    def make_class_dependency_graph(self, classes: List[Type]):
        """
        Create a direct acyclic graph containing the class hierarchy.
        """
        self.class_dependency_graph = nx.DiGraph()

        for clazz in classes:
            self.class_dependency_graph.add_node(clazz)

            for base in clazz.__bases__:
                if base in classes:
                    self.class_dependency_graph.add_edge(base, clazz)

    def make_all_tables(self) -> Dict[Type, Mapper]:
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
        for f in fields(wrapped_table.clazz):

            if wrapped_table.parent_class and f in fields(wrapped_table.parent_class.clazz):
                continue

            self.parse_field(wrapped_table, f)

    def parse_field(self, wrapped_table: WrappedTable, f: Field):
        """
        Parse a single field.
        This is done by checking the type information of a field and delegating it to the correct method.

        :param wrapped_table: The WrappedTable object where the field is in the clazz attribute
        :param f: The field to parse
        """

        logger.info("=" * 80)
        logger.info(f"Processing Field {wrapped_table.clazz.__name__}.{f.name}: {f.type}.")

        if f.name.startswith("_"):
            logger.info(f"Skipping.")
            return

        field_info = FieldInfo(wrapped_table.clazz, f)

        if field_info.is_type_type:
            logger.info(f"Parsing as type.")
            type_type = TypeType
            column = Column(field_info.name, type_type)
            wrapped_table.columns.append(column)
            wrapped_table.custom_types.append(CustomTypeInfo(column, type_type, field_info))

        elif field_info.is_builtin_class or field_info.is_enum or field_info.is_datetime:
            logger.info(f"Parsing as builtin type.")
            wrapped_table.columns.append(field_info.column)
        elif field_info.type in self.type_mappings:
            logger.info(f"Parsing as custom type mapping.")
            self.create_custom_type_column(wrapped_table, field_info)
        elif not field_info.container and (
                field_info.type in self.class_dict or field_info.type in self.type_mappings.keys()):
            logger.info(f"Parsing as one to one relationship.")
            self.create_one_to_one_relationship(wrapped_table, field_info)
        elif field_info.container:
            logger.info(f"Parsing as one to many relationship.")
            self.parse_container_field(wrapped_table, field_info)
        else:
            logger.info("Skipping due to not handled type.")

    def foreign_key_name(self, field_info: FieldInfo):
        """
        :return: A foreign key name for the given field.
        """
        return f"{field_info.clazz.__name__.lower()}_{field_info.name}{self.foreign_key_postfix}"

    def create_one_to_one_relationship(self, wrapped_table: WrappedTable, field_info: FieldInfo):
        """
        Create a one-to-one relationship between two tables.

        The relationship is created using a foreign key column and a relationship property on `wrapped_table` and
         a relationship property on the `field.type` table.

        :param wrapped_table: The table that the relationship will be created on
        :param field_info: The field that the relationship will be created for
        """

        fk_name = f"{field_info.name}{self.foreign_key_postfix}"

        other_wrapped_table = self.class_dict[field_info.type]

        # create a foreign key to field.type
        column = sqlalchemy.Column(fk_name, Integer, sqlalchemy.ForeignKey(other_wrapped_table.full_primary_key_name),
                                   nullable=field_info.optional)
        wrapped_table.columns.append(column)

        # if it is an ordinary one-to-one relationship
        if wrapped_table.clazz != other_wrapped_table.clazz:
            relationship_ = sqlalchemy.orm.relationship(other_wrapped_table.clazz, foreign_keys=[column])
            relationship_info = RelationshipInfo(relationship=relationship_, field_info=field_info,
                                                 foreign_key_name=fk_name)
        else:
            # handle self-referencing relationship
            relationship_ = sqlalchemy.orm.relationship(wrapped_table.clazz, remote_side=[wrapped_table.primary_key],
                                                        foreign_keys=[column])

            relationship_info = RelationshipInfo(relationship=relationship_, field_info=field_info,
                                                 foreign_key_name=fk_name)
        wrapped_table.one_to_one_relationships.append(relationship_info)

    def create_custom_type_column(self, wrapped_table: WrappedTable, field_info: FieldInfo):
        custom_type = self.type_mappings[field_info.type]
        column = sqlalchemy.Column(field_info.name, custom_type, nullable=field_info.optional)
        wrapped_table.columns.append(column)
        r = [column for column in wrapped_table.columns if column.name == field_info.name][0]
        custom_type_info = CustomTypeInfo(custom_type=custom_type, field_info=field_info, column=r)
        wrapped_table.custom_types.append(custom_type_info)

    def parse_container_field(self, wrapped_table: WrappedTable, field_info: FieldInfo):
        """
        Parse an iterable field and create a one-to-many relationship if needed.

        :param wrapped_table: The table that the relationship will be created on
        :param field_info: The field to parse
        """

        if field_info.type in self.class_dict:
            self.create_one_to_many_relationship(wrapped_table, field_info)

        elif field_info.is_container_of_builtin:
            column = sqlalchemy.Column(field_info.name, JSON)
            wrapped_table.columns.append(column)

        else:
            raise ParseError(f"Could not parse iterable field {field}")

    def create_one_to_many_relationship(self, wrapped_table: WrappedTable, field_info: FieldInfo):
        """
        Create a one-to-many relationship between two tables.
        The relationship is created using a foreign key column on `field_info.type` and a
        relationship property on `WrappedTable.clazz`.

        :param wrapped_table: The "one" side of the relationship.
        :param field_info: The "many" side of the relationship.
        """
        child_wrapped_table = self.class_dict[field_info.type]

        # add a foreign key to the other table describing this table
        fk_name = self.foreign_key_name(field_info)
        fk = sqlalchemy.Column(fk_name, Integer, sqlalchemy.ForeignKey(wrapped_table.full_primary_key_name),
                               nullable=True)
        child_wrapped_table.columns.append(fk)

        # add a relationship to this table holding the list of objects from the field.type table
        relationship_ = sqlalchemy.orm.relationship(field_info.type, default_factory=field_info.container,
                                                    foreign_keys=[fk])
        relationship_info = RelationshipInfo(foreign_key_name=fk_name, relationship=relationship_,
                                             field_info=field_info, )
        wrapped_table.one_to_many_relationships.append(relationship_info)

    def to_python_file(self, generator: sqlacodegen.generators.TablesGenerator, file: TextIO):
        # monkeypatch the render_column_type method to handle Enum types as desired
        generator.render_column_type_old = generator.render_column_type
        generator.render_column_type = render_enum_aware_column_type.__get__(generator,
                                                                             sqlacodegen.generators.TablesGenerator)

        # collect imports
        generator.module_imports |= {clazz.explicit_mapping.__module__ for clazz in self.class_dict.keys() if
                                     issubclass(clazz, ORMaticExplicitMapping)}
        generator.module_imports |= {clazz.__module__ for clazz in self.class_dict.keys()}
        generator.imports["sqlalchemy.orm"] = {"registry", "relationship", "RelationshipProperty"}

        # write tables
        file.write(generator.generate())

        # add registry
        file.write("\n")
        file.write("mapper_registry = registry(metadata=metadata)\n")

        # write imperative mapping calls
        for wrapped_table in self.class_dict.values():
            file.write("\n")

            parsed_kwargs = wrapped_table.mapper_kwargs_for_python_file(self)
            if issubclass(wrapped_table.clazz, ORMaticExplicitMapping):
                key = wrapped_table.clazz.explicit_mapping
            else:
                key = wrapped_table.clazz

            file.write(f"m_{wrapped_table.tablename} = mapper_registry."
                       f"map_imperatively({key.__module__}.{key.__name__}, "
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

    mapper_registry: registry
    """
    The SQLAlchemy mapper registry. This is needed for the relationship configuration.
    """

    columns: List[Column] = field(default_factory=list)
    """
    A list of columns that will be added to the SQLAlchemy table.
    """

    one_to_one_relationships: List[RelationshipInfo] = field(default_factory=list)
    """
    A list of one-to-one relationships that will be added to the SQLAlchemy table."""

    one_to_many_relationships: List[RelationshipInfo] = field(default_factory=list)
    """
    A list of one-to-many relationships that will be added to the SQLAlchemy table.
    """

    custom_types: List[CustomTypeInfo] = field(default_factory=list)
    """
    A list of custom column types that will be added to the SQLAlchemy table.
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

    @cached_property
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
        return self.has_subclasses and not self.parent_class

    @property
    def properties_kwargs(self) -> Dict[str, Any]:
        """
        :return: A dict of properties that can be used in the `mapper_kwargs`
        """
        return {**self.relationships_kwargs, **self.custom_type_kwargs}

    @property
    def relationships_kwargs(self) -> Dict[str, Any]:
        """
        :return: A dict of relationship properties that can be used in the `properties`
        """
        result = {}
        for relationship_info in self.one_to_one_relationships:
            result[relationship_info.field_info.name] = relationship_info.relationship
        for relationship_info in self.one_to_many_relationships:
            result[relationship_info.field_info.name] = relationship_info.relationship
        return result

    @property
    def custom_type_kwargs(self) -> Dict[str, Any]:
        """
        :return: A dict of custom type properties that can be used in the `properties
        """
        result = {}
        for custom_type in self.custom_types:
            result[custom_type.field_info.name] = custom_type.column
        return result

    @property
    def mapper_kwargs(self):
        kwargs = {"properties": self.properties_kwargs}

        if self.is_root_of_non_empty_inheritance_structure:
            kwargs["polymorphic_on"] = self.polymorphic_on_name
            kwargs["polymorphic_identity"] = self.tablename
        elif self.parent_class:
            kwargs["polymorphic_identity"] = self.tablename
            kwargs["inherits"] = self.parent_class.mapped_table

        return kwargs

    def mapper_kwargs_for_python_file(self, ormatic: ORMatic) -> str:
        result = {}
        properties = {}

        for relationship_info in self.one_to_one_relationships:
            foreign_key_constraint = f"t_{self.tablename}.c.{relationship_info.field_info.name}_id"
            properties[relationship_info.field_info.name] = (
                f"relationship('{relationship_info.field_info.type.__name__}',"
                f"foreign_keys=[{foreign_key_constraint}])")

        for relationship_info in self.one_to_many_relationships:
            foreign_key_constraint = f"t_{ormatic.class_dict[relationship_info.relationship.argument].tablename}.c.{relationship_info.foreign_key_name}"
            properties[relationship_info.field_info.name] = (
                f"relationship('{relationship_info.field_info.type.__name__}',"
                f"foreign_keys=[{foreign_key_constraint}])")

        for custom_type_info in self.custom_types:
            properties[custom_type_info.field_info.name] = f"t_{self.tablename}.c.{custom_type_info.field_info.name}"

        if properties:
            result["properties"] = "dict(" + ", \n".join(f"{p}={v}" for p, v in properties.items()) + ")"

        if self.is_root_of_non_empty_inheritance_structure:
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
        if self.is_root_of_non_empty_inheritance_structure:
            columns.append(Column(self.polymorphic_on_name, sqlalchemy.String))

        table = Table(self.tablename, self.mapper_registry.metadata, *columns, )

        if issubclass(self.clazz, ORMaticExplicitMapping):
            clazz = self.clazz.explicit_mapping
        else:
            clazz = self.clazz

        table = self.mapper_registry.map_imperatively(clazz, table, **self.mapper_kwargs)
        return table

    def __hash__(self):
        return hash(self.clazz)


def render_enum_aware_column_type(self: sqlacodegen.generators.TablesGenerator, coltype: object) -> str:
    """
    Render a column type, handling Enum types as imported enums.
    This is a drop in replacement for the TablesGenerator.render_column_type method.

    :param self: The TablesGenerator instance
    :param coltype: The column type to render
    :return: The rendered column type
    """
    if not isinstance(coltype, sqlalchemy.Enum):
        return self.render_column_type_old(coltype)
    return f"Enum({coltype.python_type.__module__}.{coltype.python_type.__name__})"
