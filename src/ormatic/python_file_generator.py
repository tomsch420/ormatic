from __future__ import annotations

import logging
from typing import TextIO, Dict, Any

import sqlalchemy
import sqlacodegen.generators
from sqlalchemy.orm import registry

from .utils import ORMaticExplicitMapping

logger = logging.getLogger(__name__)


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


class PythonFileGenerator:
    """
    A class for generating Python files from ORMatic models.
    """

    def __init__(self, ormatic):
        """
        Initialize the PythonFileGenerator with a reference to the ORMatic instance.

        :param ormatic: The ORMatic instance that created this PythonFileGenerator.
        """
        self.ormatic = ormatic

    def to_python_file(self, generator: sqlacodegen.generators.TablesGenerator, file: TextIO):
        """
        Generate a Python file from the ORMatic models.

        :param generator: The TablesGenerator instance
        :param file: The file to write to
        """
        # monkeypatch the render_column_type method to handle Enum types as desired
        generator.render_column_type_old = generator.render_column_type
        generator.render_column_type = render_enum_aware_column_type.__get__(generator,
                                                                           sqlacodegen.generators.TablesGenerator)

        # collect imports
        generator.module_imports |= {clazz.explicit_mapping.__module__ for clazz in self.ormatic.class_dict.keys() if
                                   issubclass(clazz, ORMaticExplicitMapping)}
        generator.module_imports |= {clazz.__module__ for clazz in self.ormatic.class_dict.keys()}
        # Add imports for subclasses
        generator.module_imports |= {clazz.explicit_mapping.__module__ for clazz in self.ormatic.subclass_dict.keys() if
                                   issubclass(clazz, ORMaticExplicitMapping)}
        generator.module_imports |= {clazz.__module__ for clazz in self.ormatic.subclass_dict.keys()}
        generator.imports["sqlalchemy.orm"] = {"registry", "relationship", "RelationshipProperty"}

        # write tables
        file.write(generator.generate())

        # add registry
        file.write("\n")
        file.write("mapper_registry = registry(metadata=metadata)\n")

        # write imperative mapping calls for original classes
        for wrapped_table in self.ormatic.class_dict.values():
            if wrapped_table.clazz in self.ormatic.explicitly_mapped_classes.keys():
                continue
            file.write("\n")

            parsed_kwargs = self.mapper_kwargs_for_python_file(wrapped_table)
            if issubclass(wrapped_table.clazz, ORMaticExplicitMapping):
                key = wrapped_table.clazz.explicit_mapping
            else:
                key = wrapped_table.clazz

            file.write(f"m_{wrapped_table.tablename} = mapper_registry."
                     f"map_imperatively({key.__module__}.{key.__name__}, "
                     f"t_{wrapped_table.tablename}, {parsed_kwargs})\n")

        # write imperative mapping calls for subclasses
        for wrapped_table in self.ormatic.subclass_dict.values():
            if wrapped_table.clazz in self.ormatic.explicitly_mapped_classes.keys():
                continue
            file.write("\n")

            parsed_kwargs = self.mapper_kwargs_for_python_file(wrapped_table)
            if issubclass(wrapped_table.clazz, ORMaticExplicitMapping):
                key = wrapped_table.clazz.explicit_mapping
            else:
                key = wrapped_table.clazz

            file.write(f"m_{wrapped_table.tablename} = mapper_registry."
                     f"map_imperatively({key.__module__}.{key.__name__}, "
                     f"t_{wrapped_table.tablename}, {parsed_kwargs})\n")

    def mapper_kwargs_for_python_file(self, wrapped_table) -> str:
        """
        Generate mapper kwargs for a wrapped table.

        :param wrapped_table: The wrapped table
        :return: A string representation of the mapper kwargs
        """
        result = {}
        properties = {}

        # For subclasses that are not in the original list, return minimal properties
        if wrapped_table.clazz in self.ormatic.subclass_dict and wrapped_table.clazz not in self.ormatic.original_classes:
            # Only include inheritance-related properties
            pass
        else:
            # Process relationships and custom types for original classes
            for relationship_info in wrapped_table.one_to_one_relationships:
                foreign_key_constraint = f"t_{wrapped_table.tablename}.c.{relationship_info.field_info.name}_id"
                properties[relationship_info.field_info.name] = (
                    f"relationship('{relationship_info.field_info.type.__name__}',"
                    f"foreign_keys=[{foreign_key_constraint}])")

            for relationship_info in wrapped_table.one_to_many_relationships:
                # Get the wrapped table from either class_dict or subclass_dict
                related_wrapped_table = self.ormatic.class_dict.get(relationship_info.relationship.argument) or self.ormatic.subclass_dict.get(relationship_info.relationship.argument)
                if related_wrapped_table:
                    foreign_key_constraint = f"t_{related_wrapped_table.tablename}.c.{relationship_info.foreign_key_name}"
                    properties[relationship_info.field_info.name] = (
                        f"relationship('{relationship_info.field_info.type.__name__}',"
                        f"foreign_keys=[{foreign_key_constraint}])")

            for custom_type_info in wrapped_table.custom_types:
                properties[custom_type_info.field_info.name] = f"t_{wrapped_table.tablename}.c.{custom_type_info.field_info.name}"

        if properties:
            result["properties"] = "dict(" + ", \n".join(f"{p}={v}" for p, v in properties.items()) + ")"

        if wrapped_table.is_root_of_non_empty_inheritance_structure:
            result["polymorphic_on"] = f"\"{wrapped_table.polymorphic_on_name}\""
            result["polymorphic_identity"] = f"\"{wrapped_table.tablename}\""
        if wrapped_table.parent_class:
            result["polymorphic_identity"] = f"\"{wrapped_table.tablename}\""
            result["inherits"] = f"m_{wrapped_table.parent_class.tablename}"

        result = ", ".join(f"{key} = {value}" for key, value in result.items())
        return result
