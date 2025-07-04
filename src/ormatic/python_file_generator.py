from __future__ import annotations

import logging
import types
from typing import TextIO, Type, TYPE_CHECKING

import sqlacodegen.generators
import sqlalchemy
from sqlacodegen.models import RelationshipAttribute, RelationshipType

from .dao import DataAccessObject
if TYPE_CHECKING:
    from .ormatic import ORMatic


logger = logging.getLogger(__name__)


def render_class_declaration_dao(self, model) -> str:
    parent_class_name = (
        model.parent_class.name if model.parent_class else self.base_class_name
    )
    # add the DAO mixin and exclude the DAO suffix for the template.
    # Only add DataAccessObject if the parent class is not already a DAO class
    if parent_class_name.endswith("DAO"):
        return f"class {model.name}({parent_class_name}):"
    else:
        return f"class {model.name}({parent_class_name}, DataAccessObject[{model.name[:-3]}]):"


def render_enum_aware_column_type(self, coltype) -> str:
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


def generate_relationship_name_from_ormatic(self, relationship: RelationshipAttribute,
                                            global_names: set[str], local_names: set[str]):
    self.generate_relationship_name_old(relationship, global_names, local_names)
    # print("------------------ generate_relationship_name ------------------")
    # if relationship.type == RelationshipType.ONE_TO_MANY:
    #     # get the table for the relationship.source.name in the ormatic
    #     for wrapped_table in self.ormatic.class_dict.values():
    #         if wrapped_table.tablename == relationship.source.table.name:
    #             for name, rel in wrapped_table.relationships_kwargs.items():
    #                 print(rel, relationship.foreign_keys)


class PythonFileGenerator:
    """
    A class for generating Python files from ORMatic models.
    """

    ormatic: ORMatic

    def __init__(self, ormatic):
        """
        Initialize the PythonFileGenerator with a reference to the ORMatic instance.

        :param ormatic: The ORMatic instance that created this PythonFileGenerator.
        """
        self.ormatic = ormatic

    def apply_monkey_patch(self, generator: sqlacodegen.generators.DeclarativeGenerator):
        """
        Monkey patches the methods of the generator to reflect the relevant changes with ORMatic.

        :param generator: The generator to monkey-patch
        """
        generator.ormatic = self.ormatic
        generator.render_class_declaration_old = generator.render_class_declaration
        generator.render_class_declaration = types.MethodType(
            render_class_declaration_dao,  generator
        )

        generator.render_column_type_old = generator.render_column_type
        generator.render_column_type = types.MethodType(
            render_enum_aware_column_type, generator
        )

        generator.generate_relationship_name_old = generator.generate_relationship_name
        generator.generate_relationship_name = types.MethodType(
            generate_relationship_name_from_ormatic, generator
        )

    def to_python_file(self, generator: sqlacodegen.generators.DeclarativeGenerator, file: TextIO):
        """
        Generate a Python file from the ORMatic models.

        :param generator: The TablesGenerator instance
        :param file: The file to write to
        """

        self.apply_monkey_patch(generator)

        # generate imports of mapped classes
        for clazz in self.ormatic.class_dict.keys():
            clazz: Type
            generator.imports[clazz.__module__] |= {clazz.__name__}

        generator.imports["ormatic.dao"] = {DataAccessObject.__name__}

        # Generate the code
        code = generator.generate()
        # write tables
        file.write(code)
