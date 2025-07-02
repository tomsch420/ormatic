from __future__ import annotations

import logging
from dataclasses import Field
from typing import Any, Dict, Type

import sqlalchemy
from sqlalchemy import Column, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from typing_extensions import List, Optional

from .field_info import FieldInfo, RelationshipInfo, CustomTypeInfo
from .custom_types import TypeType

logger = logging.getLogger(__name__)


class FieldParser:
    """
    A class for parsing fields in dataclasses and creating appropriate SQLAlchemy columns and relationships.
    """

    def __init__(self, ormatic):
        """
        Initialize the FieldParser with a reference to the ORMatic instance.
        
        :param ormatic: The ORMatic instance that created this FieldParser.
        """
        self.ormatic = ormatic

    def parse_field(self, wrapped_table, f: Field):
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
        elif field_info.type in self.ormatic.type_mappings:
            logger.info(f"Parsing as custom type mapping.")
            self.create_custom_type_column(wrapped_table, field_info)
        elif not field_info.container and (
                field_info.type in self.ormatic.class_dict
                or field_info.type in self.ormatic.subclass_dict
                or field_info.type in self.ormatic.type_mappings.keys()
        ):
            logger.info(f"Parsing as one to one relationship.")
            self.create_one_to_one_relationship(wrapped_table, field_info)
        elif field_info.container:
            logger.info(f"Parsing as one to many relationship.")
            self.parse_container_field(wrapped_table, field_info)
        else:
            logger.info("Skipping due to not handled type.")

    def parse_container_field(self, wrapped_table, field_info: FieldInfo):
        """
        Parse an iterable field and create a one-to-many relationship if needed.

        :param wrapped_table: The table that the relationship will be created on
        :param field_info: The field to parse
        """
        if field_info.type in self.ormatic.class_dict or field_info.type in self.ormatic.subclass_dict:
            self.create_one_to_many_relationship(wrapped_table, field_info)

        elif field_info.is_container_of_builtin:
            column = sqlalchemy.Column(field_info.name, JSON)
            wrapped_table.columns.append(column)

        else:
            logger.info(f"Could not parse iterable field {field_info} of class {wrapped_table.clazz}")

    def create_one_to_one_relationship(self, wrapped_table, field_info: FieldInfo):
        """
        Create a one-to-one relationship between two tables.

        The relationship is created using a foreign key column and a relationship property on `wrapped_table` and
         a relationship property on the `field.type` table.

        :param wrapped_table: The table that the relationship will be created on
        :param field_info: The field that the relationship will be created for
        """
        fk_name = f"{field_info.name}{self.ormatic.foreign_key_postfix}"

        # Get the wrapped table from either class_dict or subclass_dict
        other_wrapped_table = self.ormatic.class_dict.get(field_info.type) or self.ormatic.subclass_dict.get(field_info.type)

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

    def create_one_to_many_relationship(self, wrapped_table, field_info: FieldInfo):
        """
        Create a one-to-many relationship between two tables.
        The relationship is created using a foreign key column on `field_info.type` and a
        relationship property on `WrappedTable.clazz`.

        :param wrapped_table: The "one" side of the relationship.
        :param field_info: The "many" side of the relationship.
        """
        # Get the wrapped table from either class_dict or subclass_dict
        child_wrapped_table = self.ormatic.class_dict.get(field_info.type) or self.ormatic.subclass_dict.get(field_info.type)

        # Check if the field type is a parent class of the current class
        is_parent_class = issubclass(wrapped_table.clazz, field_info.type)

        # add a foreign key to the other table describing this table
        fk_name = self.foreign_key_name(field_info)
        fk = sqlalchemy.Column(fk_name, Integer, sqlalchemy.ForeignKey(wrapped_table.full_primary_key_name),
                               nullable=True)

        # Only add the foreign key to the child table if it's not a parent class
        if not is_parent_class:
            child_wrapped_table.columns.append(fk)

        # add a relationship to this table holding the list of objects from the field.type table
        relationship_kwargs = {
            "default_factory": field_info.container,
        }

        if is_parent_class:
            # For self-referential relationships (when the field type is a parent class)
            relationship_kwargs["primaryjoin"] = f"{wrapped_table.full_primary_key_name} == foreign({child_wrapped_table.full_primary_key_name})"
            relationship_kwargs["remote_side"] = [child_wrapped_table.primary_key]
        else:
            relationship_kwargs["foreign_keys"] = [fk]

        relationship_ = sqlalchemy.orm.relationship(field_info.type, **relationship_kwargs)
        relationship_info = RelationshipInfo(foreign_key_name=fk_name, relationship=relationship_,
                                             field_info=field_info, )
        wrapped_table.one_to_many_relationships.append(relationship_info)

    def create_custom_type_column(self, wrapped_table, field_info: FieldInfo):
        """
        Create a column for a custom type.

        :param wrapped_table: The table that the column will be added to
        :param field_info: The field that the column will be created for
        """
        custom_type = self.ormatic.type_mappings[field_info.type]
        column = sqlalchemy.Column(field_info.name, custom_type, nullable=field_info.optional)
        wrapped_table.columns.append(column)
        r = [column for column in wrapped_table.columns if column.name == field_info.name][0]
        custom_type_info = CustomTypeInfo(custom_type=custom_type, field_info=field_info, column=r)
        wrapped_table.custom_types.append(custom_type_info)

    def foreign_key_name(self, field_info: FieldInfo):
        """
        :return: A foreign key name for the given field.
        """
        return f"{field_info.clazz.__name__.lower()}_{field_info.name}{self.ormatic.foreign_key_postfix}"