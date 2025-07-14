from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field, fields, Field, is_dataclass
from functools import cached_property, lru_cache
from typing import Any, Optional, Tuple, Set
from typing import TextIO

import rustworkx as rx
from sqlalchemy import TypeDecorator
from typing_extensions import List, Type, Dict

from .dao import AlternativeMapping
from .field_info import FieldInfo
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

    imports: Set[str]
    """
    A set of modules that need to be imported.
    """

    extra_imports: Dict[str, Set[str]]
    """
    A dict that maps modules to classes that should be imported via from module import class.
    The key is the module, the value is the set of classes that are needed
    """

    type_mappings: Dict[Type, TypeDecorator]
    """
    A dict that maps classes to custom types that should be used to save the classes.
    They keys of the type mappings must be disjoint with the classes given..
    """

    type_annotation_map: Dict[str, str]
    """
    The string version of type mappings that is used in jinja.
    """

    def __init__(self, classes: List[Type],
                 type_mappings: Dict[Type, TypeDecorator] = None):
        """
        :param classes: The list of classes to be mapped.
        :param type_mappings: A dict that maps classes to custom types that should be used instead of the class.
        """

        if type_mappings is None:
            self.type_mappings = dict()
        else:
            intersection_of_classes_and_types = set(classes) & set(type_mappings.keys())
            if len(intersection_of_classes_and_types) > 0:
                raise ValueError(f"The type mappings given are not disjoint with the classes given."
                                 f"The intersection is {intersection_of_classes_and_types}")
            self.type_mappings = type_mappings
        self.create_type_annotations_map()

        self.class_dict = {}
        self.imports = set()
        for cls in classes:
            if issubclass(cls, AlternativeMapping):
                # if the class is a DAO, we use the original class for the mapping
                self.class_dict[cls.original_class()] = WrappedTable(clazz=cls, ormatic=self)
            else:
                self.class_dict[cls] = WrappedTable(clazz=cls, ormatic=self)
            self.imports.add(cls.__module__)

        self.make_class_dependency_graph()
        self.extra_imports = defaultdict(set)

        self.make_all_tables()

    def create_type_annotations_map(self):
        self.type_annotation_map = {
            "Type": "TypeType"
        }
        for clazz, custom_type in self.type_mappings.items():
            self.type_annotation_map[
                f"{clazz.__module__}.{clazz.__name__}"] = f"{custom_type.__module__}.{custom_type.__name__}"

    def make_class_dependency_graph(self):
        """
        Create a direct acyclic graph containing the class hierarchy.
        """
        self.class_dependency_graph = rx.PyDAG()

        for clazz, wrapped_table in self.class_dict.items():
            self._add_wrapped_table(wrapped_table)

            bases = [base for base in clazz.__bases__ if
                     base.__module__ not in ["builtins"] and base in self.class_dict]

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

    builtin_columns: List[Tuple[str, str]] = field(default_factory=list)
    """
    List of columns that can be directly mapped using builtin types
    """

    custom_columns: List[Tuple[str, str, str]] = field(default_factory=list)
    """
    List for custom columns that need to by fully qualified
    """

    foreign_keys: List[Tuple[str, str, str]] = field(default_factory=list)
    """
    List of columns that represent foreign keys
    """

    relationships: List[Tuple[str, str, str]] = field(default_factory=list)
    """
    List of relationships that should be added to the table.
    """

    mapper_args: Dict[str, str] = field(default_factory=dict)

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

    def __post_init__(self):
        if not is_dataclass(self.clazz):
            raise TypeError(f"ORMatic can only process dataclasses. Got {self.clazz} which is not a dataclass.")

    @cached_property
    def primary_key(self):
        if self.parent_table is not None:
            column_type = f"ForeignKey({self.parent_table.full_primary_key_name})"
        else:
            column_type = "Integer"

        return f"mapped_column({column_type}, primary_key=True)"

    @property
    def child_tables(self) -> List[WrappedTable]:
        return self.ormatic.class_dependency_graph.successors(self.index)

    def create_mapper_args(self):

        # this is the root of an inheritance structure
        if self.parent_table is None and len(self.child_tables) > 0:
            self.builtin_columns.append((self.polymorphic_on_name, "Mapped[str]"))
            self.mapper_args.update({
                "'polymorphic_on'": f"'{self.polymorphic_on_name}'",
                "'polymorphic_identity'": f"'{self.tablename}'",
            })

        # this inherits from something
        if self.parent_table is not None:
            self.mapper_args.update({
                "'polymorphic_identity'": f"'{self.tablename}'",
                "'inherit_condition'": f"{self.primary_key_name} == {self.parent_table.full_primary_key_name}"
            })

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

    @cached_property
    def fields(self) -> List[Field]:
        # collect parent fields TODO check the desired fields from parent classes

        skip_fields = []

        if self.parent_table is not None:
            skip_fields.extend(self.parent_table.fields)

        result = [field for field in fields(self.clazz) if field not in skip_fields]

        if self.parent_table is not None:
            if issubclass(self.parent_table.clazz, AlternativeMapping):
                og_parent_class = self.parent_table.clazz.original_class()
                fields_in_og_class_but_not_in_dao = [f for f in fields(og_parent_class)
                                                     if f not in self.parent_table.fields]

                result = [r for r in result if r not in fields_in_og_class_but_not_in_dao]

        return result

    @lru_cache(maxsize=None)
    def parse_fields(self):

        for f in self.fields:

            logger.info("=" * 80)
            logger.info(f"Processing Field {self.clazz.__name__}.{f.name}: {f.type}.")

            # skip private fields
            if f.name.startswith("_"):
                logger.info(f"Skipping since the field starts with _.")
                continue

            field_info = FieldInfo(self.clazz, f)
            self.parse_field(field_info)

        self.create_mapper_args()

    def parse_field(self, field_info: FieldInfo):
        if field_info.is_type_type:
            logger.info(f"Parsing as type.")
            self.create_type_type_column(field_info)

        elif field_info.is_builtin_class or field_info.is_enum or field_info.is_datetime:
            logger.info(f"Parsing as builtin type.")
            self.create_builtin_column(field_info)

        # handle on to one relationships
        elif not field_info.container and field_info.type in self.ormatic.class_dict:
            logger.info(f"Parsing as one to one relationship.")
            self.create_one_to_one_relationship(field_info)

        elif not field_info.container and field_info.type in self.ormatic.type_mappings:
            logger.info(f"Parsing as custom type {self.ormatic.type_mappings[field_info.type]}.")
            self.create_custom_type(field_info)

        elif field_info.container:
            if field_info.is_container_of_builtin:
                logger.info(f"Parsing as JSON.")
                self.create_container_of_builtins(field_info)
            elif field_info.type in self.ormatic.class_dict:
                logger.info(f"Parsing as one to many relationship.")
                self.create_one_to_many_relationship(field_info)
        else:
            logger.info("Skipping due to not handled type.")

    def create_builtin_column(self, field_info: FieldInfo):
        if field_info.is_enum:
            self.ormatic.extra_imports[field_info.type.__module__] |= {field_info.type.__name__}

        if not field_info.is_builtin_class:
            self.ormatic.imports |= {field_info.type.__module__}
            inner_type = f"{field_info.type.__module__}.{field_info.type.__name__}"
        else:
            inner_type = f"{field_info.type.__name__}"
        if field_info.optional:
            inner_type = f"Optional[{inner_type}]"

        self.builtin_columns.append((field_info.name, f"Mapped[{inner_type}]"))

    def create_type_type_column(self, field_info: FieldInfo):
        column_name = field_info.name
        column_type = f"Mapped[TypeType]" if not field_info.optional else f"Mapped[Optional[TypeType]]"
        column_constructor = f"mapped_column(TypeType, nullable={field_info.optional})"
        self.custom_columns.append((column_name, column_type, column_constructor))

    def create_one_to_one_relationship(self, field_info: FieldInfo):
        # create foreign key
        fk_name = f"{field_info.name}{self.ormatic.foreign_key_postfix}"
        fk_type = f"Mapped[Optional[int]]" if field_info.optional else "Mapped[int]"

        # columns have to be nullable and use_alter=True since the insertion order might be incorrect otherwise
        fk_column_constructor = f"mapped_column(ForeignKey('{self.ormatic.class_dict[field_info.type].full_primary_key_name}', use_alter=True), nullable=True)"

        self.foreign_keys.append((fk_name, fk_type, fk_column_constructor))

        # create relationship to remote side
        other_table = self.ormatic.class_dict[field_info.type]
        rel_name = f"{field_info.name}"
        rel_type = f"Mapped[{other_table.tablename}]"
        # relationships have to be post updated since since it won't work in the case of subclasses with another ref otherwise
        rel_constructor = f"relationship('{other_table.tablename}', uselist=False, foreign_keys=[{fk_name}], post_update=True)"
        self.relationships.append((rel_name, rel_type, rel_constructor))

    def create_one_to_many_relationship(self, field_info: FieldInfo):
        # create a foreign key to this on the remote side
        other_table = self.ormatic.class_dict[field_info.type]
        fk_name = f"{self.tablename.lower()}_{field_info.name}{self.ormatic.foreign_key_postfix}"
        fk_type = "Mapped[Optional[int]]"
        fk_column_constructor = f"mapped_column(ForeignKey('{self.full_primary_key_name}'))"
        other_table.foreign_keys.append((fk_name, fk_type, fk_column_constructor))

        # create a relationship with a list to collect the other side
        rel_name = f"{field_info.name}"
        rel_type = f"Mapped[List[{other_table.tablename}]]"
        rel_constructor = f"relationship('{other_table.tablename}', foreign_keys='[{other_table.tablename}.{fk_name}]')"
        self.relationships.append((rel_name, rel_type, rel_constructor))

    def create_container_of_builtins(self, field_info: FieldInfo):
        column_name = field_info.name
        container = "Set" if issubclass(field_info.container, set) else "List"
        column_type = f"Mapped[{container}[{field_info.type.__name__}]]"
        column_constructor = f"mapped_column(JSON, nullable={field_info.optional})"
        self.custom_columns.append((column_name, column_type, column_constructor))

    def create_custom_type(self, field_info: FieldInfo):
        custom_type = self.ormatic.type_mappings[field_info.type]
        column_name = field_info.name
        column_type = f"Mapped[{custom_type.__module__}.{custom_type.__name__}]" if not field_info.optional \
            else f"Mapped[Optional[{custom_type.__module__}.{custom_type.__name__}]]"

        constructor = f"mapped_column({custom_type.__module__}.{custom_type.__name__}, nullable={field_info.optional})"

        self.custom_columns.append((column_name, column_type, constructor))

    @property
    def to_dao(self) -> Optional[str]:
        if issubclass(self.clazz, AlternativeMapping):
            return f"to_dao = {self.clazz.__module__}.{self.clazz.__name__}.to_dao"
        return None

    @property
    def base_class_name(self):
        if self.parent_table is not None:
            return self.parent_table.tablename
        else:
            return "Base"

    def __hash__(self):
        return hash(self.clazz)
