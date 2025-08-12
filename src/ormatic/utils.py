from __future__ import annotations

import datetime
import inspect
import sys
from contextlib import suppress
from enum import Enum
from typing import Type, List, Iterable

import sqlalchemy
from sqlalchemy import Engine, text, MetaData


class classproperty:
    """
    A decorator that allows a class method to be accessed as a property.
    """

    def __init__(self, fget):
        self.fget = fget

    def __get__(self, instance, owner):
        return self.fget(owner)


def classes_of_module(module) -> List[Type]:
    """
    Get all classes of a given module.

    :param module: The module to inspect.
    :return: All classes of the given module.
    """

    result = []
    for name, obj in inspect.getmembers(sys.modules[module.__name__]):
        if inspect.isclass(obj) and obj.__module__ == module.__name__:
            result.append(obj)
    return result


def recursive_subclasses(cls):
    """
    :param cls: The class.
    :return: A list of the classes subclasses.
    """
    return cls.__subclasses__() + [g for s in cls.__subclasses__() for g in recursive_subclasses(s)]


leaf_types = (int, float, str, Enum, datetime.datetime, bool)


def _drop_fk_constraints(engine: Engine, tables: Iterable[str]) -> None:
    """
    Drops foreign key constraints for the specified tables in the given engine.

    This function removes all foreign key constraints for the specified list
    of tables using the provided database engine. It supports multiple
    SQL dialects, including MySQL, PostgreSQL, SQLite, and others.

    :param engine: The SQLAlchemy Engine instance used to interact with
        the database.
    :param tables: An iterable of table names whose foreign key constraints
        need to be dropped.
    """
    insp = sqlalchemy.inspect(engine)
    dialect = engine.dialect.name.lower()

    with engine.begin() as conn:
        for table in tables:
            for fk in insp.get_foreign_keys(table):
                name = fk.get("name")
                if not name:  # unnamed FKs (e.g. SQLite)
                    continue

                if dialect.startswith("mysql"):
                    stmt = text(f"ALTER TABLE `{table}` DROP FOREIGN KEY `{name}`")
                else:  # PostgreSQL, SQLite, MSSQL, …
                    stmt = text(f'ALTER TABLE "{table}" DROP CONSTRAINT "{name}"')

                with suppress(Exception):
                    conn.execute(stmt)


def drop_database(engine: Engine) -> None:
    """
    Drops all tables in the given database engine. This function removes foreign key
    constraints and tables in reverse dependency order to ensure that proper
    dropping of objects occurs without conflict. For MySQL/MariaDB, foreign key
   checks are disabled temporarily during the process.

    This method differs from sqlalchemy `MetaData.drop_all <https://docs.sqlalchemy.org/en/20/core/metadata.html#sqlalchemy.schema.MetaData.drop_all>`_\ such that databases containing cyclic
    backreferences are also droppable.

    :param engine: The SQLAlchemy Engine instance connected to the target database
        where tables will be dropped.
    :type engine: Engine
    :return: None
    """
    metadata = MetaData()
    metadata.reflect(bind=engine)

    if not metadata.tables:
        return

    # 1. Drop FK constraints that would otherwise block table deletion.
    _drop_fk_constraints(engine, metadata.tables.keys())

    # 2. On MySQL / MariaDB it is still safest to disable FK checks entirely
    #    while the DROP TABLE statements run; other back-ends don’t need this.
    disable_fk_checks = engine.dialect.name.lower().startswith("mysql")

    with engine.begin() as conn:
        if disable_fk_checks:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        # Drop in reverse dependency order (children first → parents last).
        for table in reversed(metadata.sorted_tables):
            table.drop(bind=conn, checkfirst=True)

        if disable_fk_checks:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
