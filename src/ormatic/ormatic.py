from __future__ import annotations

import logging
from dataclasses import dataclass, Field, fields, field
from functools import cached_property
from typing import Any
from typing import TextIO

import networkx as nx

try:
    import sqlacodegen.generators
except ImportError:
    logging.warn("sqlacodegen is not available. Writing the ORMatic to python files will not be available.")
    sqlacodegen = None

import sqlalchemy
from sqlalchemy import Table, Integer, Column, ForeignKey, JSON
from sqlalchemy.orm import relationship, registry, Mapper
from typing_extensions import List, Type, Dict, Optional

from .custom_types import TypeType
from .field_info import ParseError, FieldInfo, RelationshipInfo, CustomTypeInfo
from .parsers import FieldParser
from .python_file_generator import PythonFileGenerator
from .utils import ORMaticExplicitMapping, recursive_subclasses

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

    class_dependency_graph: Optional[nx.DiGraph] = None
    """
    A direct acyclic graph containing the class hierarchy.
    """

    explicitly_mapped_classes: dict = None
    """
    A dict of classes that are explicitly mapped to SQLAlchemy tables.
    """

    def __init__(self, classes: List[Type], mapper_registry: registry, type_mappings: Dict[Type, Any] = None):
        """
        :param classes: The list of classes to be mapped.
        :param mapper_registry: The SQLAlchemy mapper registry. This is needed for the relationship configuration.
        """

        #  initialize the instance variables
        self.type_mappings = type_mappings or {}
        self.mapper_registry = mapper_registry
        self.class_dict = {}

        self.explicitly_mapped_classes = {}
        self.original_classes = set(classes)

        # Create helper instances
        self.field_parser = FieldParser(self)
        self.python_file_generator = PythonFileGenerator(self)

        # create the class dependency graph
        self.make_class_dependency_graph(classes)

        # create the classes in dependency-resolved order
        for clazz in nx.topological_sort(self.class_dependency_graph):

            # get the inheritance tree
            bases: List[Type] = [base for (base, _) in self.class_dependency_graph.in_edges(clazz)]
            if len(bases) > 1:
                logger.warning(f"Class {clazz.__name__} has multiple inheritance. "
                               f"Only the {bases[0].__name__} one will be available for polymorphic selection.")

            base = self.class_dict.get(bases[0]) if bases else None

            # wrap the classes to aggregate the needed properties before compiling it with sql
            wrapped_table = WrappedTable(clazz=clazz, mapper_registry=mapper_registry, parent_class=base, ormatic=self)

            # Add to appropriate dictionary based on whether it's in the original classes
            if clazz in self.original_classes:
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

        # Find all subclasses of the provided classes
        all_subclasses = set()
        for clazz in classes:
            all_subclasses.update(recursive_subclasses(clazz))

        # Add all classes and their subclasses to the graph
        all_classes = set(classes) | all_subclasses

        for clazz in all_classes:
            if issubclass(clazz, ORMaticExplicitMapping):
                clazz_explicit = clazz.explicit_mapping
                # TODO duplicate check
                self.explicitly_mapped_classes[clazz_explicit] = clazz
                self.class_dependency_graph.add_node(clazz_explicit)
            self.class_dependency_graph.add_node(clazz)

            for base in clazz.__bases__:
                if base in all_classes:
                    self.class_dependency_graph.add_edge(base, clazz)

    def make_all_tables(self) -> Dict[Type, Mapper]:
        """
        Create all the SQLAlchemy tables from the classes in the class_dict

        :return: A dictionary mapping classes to their corresponding SQLAlchemy tables.
        """
        result = {}

        # Create a set of classes that are targets of explicit mappings
        explicit_mapping_targets = set(self.explicitly_mapped_classes.values())

        # Add tables from class_dict
        for wrapped_table in self.class_dict.values():
            # Skip classes that are targets of explicit mappings
            if wrapped_table.clazz not in explicit_mapping_targets:
                result[wrapped_table.clazz] = wrapped_table.mapped_table

        return result

    def parse_classes(self):
        """
        Parse all the classes in the class_dict, aggregating the columns, primary keys, foreign keys and relationships.
        """
        # Parse classes in the original class_dict
        for wrapped_table in self.class_dict.values():
            # Parse all classes, including those that implement ORMaticExplicitMapping
            self.parse_class(wrapped_table)


    def parse_class(self, wrapped_table: WrappedTable):
        """
        Parse a single class.

        :param wrapped_table: The WrappedTable object to parse
        """
        # Skip parsing fields for classes that were not in the original list
        if wrapped_table.clazz not in self.original_classes and wrapped_table.clazz not in self.explicitly_mapped_classes.keys():
            logger.info(f"Skipping fields for {wrapped_table.clazz.__name__} as it was not in the original class list")
            return

        for f in fields(wrapped_table.clazz):
            if wrapped_table.parent_class and f in fields(wrapped_table.parent_class.clazz):
                continue
            elif wrapped_table.clazz.__bases__ and wrapped_table.clazz.__bases__[0] in self.explicitly_mapped_classes.keys() \
                    and f.name not in{fld.name for fld in fields(self.explicitly_mapped_classes[wrapped_table.clazz.__bases__[0]])}:
                continue

            self.field_parser.parse_field(wrapped_table, f)

    def foreign_key_name(self, field_info: FieldInfo):
        """
        :return: A foreign key name for the given field.
        """
        return f"{field_info.clazz.__name__.lower()}_{field_info.name}{self.foreign_key_postfix}"

    def to_python_file(self, generator: sqlacodegen.generators.DataclassGenerator, file: TextIO):
        """
        Generate a Python file from the ORMatic models.

        :param generator: The TablesGenerator instance
        :param file: The file to write to
        """
        self.python_file_generator = PythonFileGenerator(self)
        self.python_file_generator.to_python_file(generator, file)


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

    ormatic: Any = None
    """
    Reference to the ORMatic instance that created this WrappedTable.
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
        if issubclass(self.clazz, ORMaticExplicitMapping):
            result = self.clazz.explicit_mapping.__name__
        else: result = self.clazz.__name__
        result += "DAO"
        return result

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
        # Only consider subclasses that are in the original list of classes
        if self.ormatic and self.subclasses:
            original_subclasses = [s for s in self.subclasses if s.clazz in self.ormatic.original_classes]
            return len(original_subclasses) > 0 and not self.parent_class
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
            # Use the polymorphic_type column as the discriminator
            kwargs["polymorphic_on"] = "polymorphic_type"
            kwargs["polymorphic_identity"] = f"{self.clazz.__module__}.{self.clazz.__name__}"
        elif self.parent_class:
            kwargs["polymorphic_identity"] = f"{self.clazz.__module__}.{self.clazz.__name__}"
            kwargs["inherits"] = self.parent_class.mapped_table

        # print("=" * 80)
        # print(self.clazz)
        # print(kwargs)
        # print("=" * 80)
        return kwargs

    def mapper_kwargs_for_python_file(self, ormatic: ORMatic) -> str:
        """
        Generate mapper kwargs for a wrapped table.

        :param ormatic: The ORMatic instance
        :return: A string representation of the mapper kwargs
        """
        return ormatic.python_file_generator.mapper_kwargs_for_python_file(self)

    @cached_property
    def mapped_table(self) -> Mapper:
        """
        :return: The SQLAlchemy table created from the dataclass. Call this after all columns and relationships have been
        added to the WrappedTable.
        """

        columns = [self.primary_key] + self.columns
        if self.is_root_of_non_empty_inheritance_structure:
            columns.append(Column(self.polymorphic_on_name, sqlalchemy.String(255)))

        table = Table(self.tablename, self.mapper_registry.metadata, *columns, )

        # For explicitly mapping classes, we need to decide whether to map to the
        # explicitly mapping class itself or to its target class
        if issubclass(self.clazz, ORMaticExplicitMapping):
            # If this is an explicitly mapping class and it's in the original classes list,
            # map the table to the explicitly mapping class itself
            if self.ormatic and self.clazz in self.ormatic.original_classes:
                clazz = self.clazz
            else:
                # Otherwise, map to the target class
                clazz = self.clazz.explicit_mapping
        else:
            # For regular classes, map to the class itself
            clazz = self.clazz

        table = self.mapper_registry.map_imperatively(clazz, table, **self.mapper_kwargs)
        return table

    def __hash__(self):
        return hash(self.clazz)
