from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field, fields
from functools import cached_property, lru_cache
from typing import Any, Optional, Tuple, Set
from typing import TextIO

import rustworkx as rx
from typing_extensions import List, Type, Dict

from . import field_info
from .custom_types import TypeType
from .field_info import FieldInfo, RelationshipInfo
from .sqlalchemy_generator import SQLAlchemyGenerator

logger = logging.getLogger(__name__)


class ORMatic:
    """
    ORMatic is a tool for generating SQLAlchemy ORM models from a set of dataclasses.
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

    class_dependency_graph: rx.PyDAG[WrappedTable]
    """
    A direct acyclic graph containing the class hierarchy.
    """

    extra_imports: Dict[str, Set[str]]

    def __init__(self, classes: List[Type],
                 type_mappings: Dict[Type, Any] = None):
        """
        :param classes: The list of classes to be mapped.
        :param mapper_registry: The SQLAlchemy mapper registry. This is needed for the relationship configuration.
        """
        self.class_dict = {cls: WrappedTable(clazz=cls, ormatic=self) for cls in classes}
        self.make_class_dependency_graph()
        self.extra_imports = defaultdict(set)
        self.make_all_tables()

    def make_class_dependency_graph(self):
        """
        Create a direct acyclic graph containing the class hierarchy.
        """
        self.class_dependency_graph = rx.PyDAG()
        for clazz, wrapped_table in self.class_dict.items():
            self._add_wrapped_table(wrapped_table)

            bases = [base for base in clazz.__bases__ if base.__module__ not in ["builtins"]]

            if len(bases) == 0:
                continue

            if len(bases) > 1:
                logger.warning(f"Found more than one base class for {clazz}. Will only use the first one ({bases[0]}) "
                               f"for inheritance in SQL.")
            base = bases[0]
            self._add_wrapped_table(self.class_dict[base])
            self.class_dependency_graph.add_edge(self.class_dict[base].index, wrapped_table.index, None)

    def _add_wrapped_table(self, wrapped_table: WrappedTable):
        if wrapped_table.index is None:
            wrapped_table.index = self.class_dependency_graph.add_node(wrapped_table)

    @property
    def wrapped_tables(self) -> List[WrappedTable]:
        """
        :return: List of all tables in topological order.
        """
        result = []
        sorter = rx.TopologicalSorter(self.class_dependency_graph)
        while sorter.is_active():
            nodes = sorter.get_ready()
            result.extend([self.class_dependency_graph[n] for n in nodes])
            sorter.done(nodes)
        return result

    def make_all_tables(self):
        for table in self.wrapped_tables:
            table.parse_fields()

    def parse_classes(self):
        """
        Parse all the classes in the class_dict, aggregating the columns, primary keys, foreign keys and relationships.
        """
        # Parse classes in the original class_dict
        for wrapped_table in self.class_dict.values():
            # Parse all classes, including those that implement ORMaticExplicitMapping
            self.parse_class(wrapped_table)

    def foreign_key_name(self, field_info: FieldInfo):
        """
        :return: A foreign key name for the given field.
        """
        return f"{field_info.clazz.__name__.lower()}_{field_info.name}{self.foreign_key_postfix}"

    def to_sqlalchemy_file(self, file: TextIO):
        """
        Generate a Python file with SQLAlchemy declarative mappings from the ORMatic models.

        :param file: The file to write to
        """
        sqlalchemy_generator = SQLAlchemyGenerator(self)
        sqlalchemy_generator.to_sqlalchemy_file(file)


@dataclass
class WrappedTable:
    """
    A class that wraps a dataclass and contains all the information needed to create a SQLAlchemy table from it.
    """

    clazz: Type
    """
    The dataclass that this WrappedTable wraps.
    """

    builtin_columns: List = field(default_factory=list)
    """
    List of columns that can be directly mapped using builtin types
    """

    foreign_keys: List = field(default_factory=list)
    """
    List of columns that represent foreign keys
    """

    relationships: List = field(default_factory=list)

    primary_key_name: str = "id"
    """
    The name of the primary key column.
    """

    polymorphic_on_name: str = "polymorphic_type"
    """
    The name of the column that will be used to identify polymorphic identities if any present.
    """

    ormatic: Any = None
    """
    Reference to the ORMatic instance that created this WrappedTable.
    """

    index: int = field(default=None, init=False)
    """
    The index of self in `self.ormatic.class_dependency_graph`. 
    """

    @cached_property
    def primary_key(self):
        if self.parent_table is not None:
            column_type = f"ForeignKey({self.parent_table.full_primary_key_name})"
        else:
            column_type = "Integer"

        return f"mapped_column({column_type}, primary_key=True)"

    @cached_property
    def full_primary_key_name(self):
        return f"{self.tablename}.{self.primary_key_name}"

    @cached_property
    def tablename(self):
        result = self.clazz.__name__
        result += "DAO"
        return result

    @cached_property
    def parent_table(self) -> Optional[WrappedTable]:
        parents = self.ormatic.class_dependency_graph.predecessors(self.index)
        if len(parents) == 0:
            return None
        return parents[0]

    @lru_cache(maxsize=None)
    def parse_fields(self):

        for f in fields(self.clazz):

            logger.info("=" * 80)
            logger.info(f"Processing Field {self.clazz.__name__}.{f.name}: {f.type}.")

            if f.name.startswith("_"):
                logger.info(f"Skipping since the field starts with _.")
                continue

            # skip fields from parent classes
            if self.parent_table is not None:
                if f in fields(self.parent_table.clazz):
                    logger.info(f"Skipping since the field is part of the parent class.")
                    continue

            field_info = FieldInfo(self.clazz, f)
            self.parse_field(field_info)

    def parse_field(self, field_info: FieldInfo):
        if field_info.is_type_type:
            logger.info(f"Parsing as type.")
            raise NotImplementedError
            # type_type = TypeType
            # column = Column(field_info.name, type_type)
            # wrapped_table.columns.append(column)
            # self.custom_types.append(CustomTypeInfo(column, type_type, field_info))

        elif field_info.is_builtin_class or field_info.is_enum or field_info.is_datetime:
            logger.info(f"Parsing as builtin type.")
            self.create_builtin_column(field_info)

        # handle on to one relationships
        elif not field_info.container and field_info.type in self.ormatic.class_dict:
            logger.info(f"Parsing as one to one relationship.")
            self.create_one_to_one_relationship(field_info)

        elif field_info.type in self.ormatic.class_dict:
            logger.info(f"Parsing as custom type mapping.")

        elif field_info.container:
            ...
        else:
            logger.info("Skipping due to not handled type.")

    def create_builtin_column(self, field_info: FieldInfo):
        if field_info.is_enum:
            self.ormatic.extra_imports[field_info.type.__module__] |= {field_info.type.__name__}
        self.builtin_columns.append((field_info.name, f"Mapped[{field_info.field.type}]"))

    def create_one_to_one_relationship(self, field_info: FieldInfo):
        # create foreign key
        fk_name = f"{field_info.name}_{self.ormatic.foreign_key_postfix}"
        fk_type = "Mapped[int]"
        fk_column_constructor = f"mapped_column(ForeignKey('{self.ormatic.class_dict[field_info.type].full_primary_key_name}'))"

        self.foreign_keys.append((fk_name, fk_type, fk_column_constructor))
        print(self.foreign_keys)
        # create relationship to remote side


    @property
    def base_class_name(self):
        if self.parent_table is not None:
            return self.parent_table.tablename
        else:
            return "Base"

    def __hash__(self):
        return hash(self.clazz)
