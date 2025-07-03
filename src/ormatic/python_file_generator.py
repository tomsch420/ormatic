from __future__ import annotations

import logging
import types
from typing import TextIO, Dict, Any, Type

import sqlalchemy
import sqlacodegen.generators
from sqlalchemy.orm import registry

from .dao import DataAccessObject
from .utils import ORMaticExplicitMapping

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

    def apply_monkey_patch(self,  generator: sqlacodegen.generators.DataclassGenerator):
        """
        Monkey patches the methods of the generator to reflect the relevant changes with ORMatic.

        :param generator: The generator to monkey-patch
        """

        generator.render_class_declaration_old = generator.render_class_declaration
        generator.render_class_declaration = types.MethodType(
            render_class_declaration_dao,  # function to bind
            generator  # bind it to this instance
        )

        generator.render_column_type_old = generator.render_column_type
        generator.render_column_type = types.MethodType(
            render_enum_aware_column_type, generator
        )

    def to_python_file(self, generator: sqlacodegen.generators.DataclassGenerator, file: TextIO):
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
