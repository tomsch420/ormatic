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
    return f"class {model.name}({parent_class_name}, DataAccessObject[{model.name[:-3]}]):"


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

        # write tables
        file.write(generator.generate())
