# python
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Any, Optional

import sqlalchemy.inspection
from sqlalchemy import and_, or_, select, Select
from sqlalchemy.orm import Session

from entity_query_language.symbolic import (
    SymbolicExpression,
    Attribute,
    Comparator,
    AND,
    OR,
    An, The, HasDomain
)

from .dao import get_dao_class


class EQLTranslationError(Exception):
    """Raised when an EQL expression cannot be translated into SQLAlchemy."""


@dataclass
class EQLTranslator:
    """
    Translate an EQL query into an SQLAlchemy query.

    This assumes the query has a structure like:
    - quantifier (an/the)
        - select like (entity, setof)
            - Root Condition
                - child 1
                - child 2
                - ...

    """

    eql_query: SymbolicExpression
    session: Session

    sql_query: Optional[Select] = None
    _joined_daos: set[type] = None

    @property
    def quantifier(self):
        return self.eql_query

    @property
    def select_like(self):
        return self.eql_query._child_

    @property
    def root_condition(self):
        return self.eql_query._child_._child_

    def translate(self) -> List[Any]:
        dao_class = get_dao_class(self.select_like.selected_variable_._cls_)
        self.sql_query = select(dao_class)
        # initialize join cache
        self._joined_daos = set()
        conditions = self.translate_query(self.root_condition)
        self.sql_query = self.sql_query.where(conditions)

    def evaluate(self):
        bound_query = self.session.scalars(self.sql_query)

        # apply the quantifier
        if isinstance(self.quantifier, An):
            return bound_query.all()

        elif isinstance(self.quantifier, The):
            return bound_query.one()

        else:
            raise EQLTranslationError(f"Unknown quantifier: {type(self.quantifier)}")

    def __iter__(self):
        yield from self.evaluate()

    # --------------------------
    # Refactored translator API
    # --------------------------

    def translate_query(self, query: SymbolicExpression):
        if isinstance(query, AND):
            return self.translate_and(query)
        elif isinstance(query, OR):
            return self.translate_or(query)
        elif isinstance(query, Comparator):
            return self.translate_comparator(query)
        elif isinstance(query, Attribute):
            return self.translate_attribute(query)
        else:
            raise EQLTranslationError(f"Unknown query type: {type(query)}")

    def translate_and(self, query: AND):
        """
        Translate an eql.AND query into an sql.AND.
        :param query: EQL query
        :return: SQL expression
        """
        return and_(*[self.translate_query(c) for c in query._children_])

    def translate_or(self, query: OR):
        """
        Translate an eql.OR query into an sql.OR.
        :param query: EQL query
        :return: SQL expression
        """
        return or_(*[self.translate_query(c) for c in query._children_])

    def translate_comparator(self, query: Comparator):
        """
        Translate an eql.Comparator query into a SQLAlchemy binary expression.
        Supports ==, !=, <, <=, >, >=, and 'in'.
        """
        def to_sql_side(side):
            # Attribute -> resolved SQLA column (with joins if needed)
            if isinstance(side, Attribute):
                return self.translate_attribute(side)
            # EQL Variable/literal with domain
            if isinstance(side, HasDomain):
                return self._literal_from_variable_domain(side)
            # Plain Python literal or iterable
            return side

        left = to_sql_side(query.left)
        right = to_sql_side(query.right)

        op = query.operation
        if op == '==':
            return left == right
        elif op == '>':
            return left > right
        elif op == '<':
            return left < right
        elif op == '>=':
            return left >= right
        elif op == '<=':
            return left <= right
        elif op == '!=':
            return left != right
        elif op == 'in':
            return left.in_(right)
        else:
            raise EQLTranslationError(f"Unknown operator: {query.operation}")

    def _literal_from_variable_domain(self, var_like: HasDomain) -> Any:
        # EQL Variables/literals expose a domain where the value can be taken from.
        return next(iter(var_like._domain_)).value

    def translate_attribute(self, query: Attribute):
        """
        Translate an eql.Attribute query into an sql construct, traversing attribute chains
        and applying necessary JOINs for relationships. Returns the final SQLAlchemy column.
        """
        # Collect the attribute chain names from outermost to leaf
        names: list[str] = []
        node = query
        while isinstance(node, Attribute):
            names.append(node._attr_name_)
            node = node._child_

        # Start at the base DAO of the leaf variable
        base_cls = node._cls_
        if base_cls is None:
            raise EQLTranslationError("Attribute chain leaf does not have a class.")
        current_dao = get_dao_class(base_cls)
        if current_dao is None:
            raise EQLTranslationError(f"No DAO class found for {base_cls}.")

        # Walk the chain from the base outward
        names = list(reversed(names))
        for idx, name in enumerate(names):
            mapper = sqlalchemy.inspection.inspect(current_dao)
            # relationship keys
            rel = mapper.relationships.get(name) if hasattr(mapper.relationships, 'get') else None
            if rel is None:
                # check by iterating if .get not available
                for r in mapper.relationships:
                    if r.key == name:
                        rel = r
                        break
            if rel is not None:
                # join using explicit relationship attribute to disambiguate path
                path_key = (current_dao, name)
                if self._joined_daos is None:
                    self._joined_daos = set()
                if path_key not in self._joined_daos:
                    self.sql_query = self.sql_query.join(getattr(current_dao, name))
                    self._joined_daos.add(path_key)
                current_dao = rel.entity.class_
                continue

            # Not a relationship -> treat as column; must be terminal element
            if idx != len(names) - 1:
                raise EQLTranslationError(
                    f"Attribute '{name}' on {current_dao.__name__} is not a relationship but chain continues.")
            try:
                return getattr(current_dao, name)
            except AttributeError as e:
                raise EQLTranslationError(f"Column '{name}' not found on {current_dao.__name__}.") from e

        # If we finished the loop without returning, chain ended on a relationship, which isn't supported here
        raise EQLTranslationError("Attribute chain ended on a relationship; expected a column.")


def eql_to_sql(query: SymbolicExpression, session: Session):
    result = EQLTranslator(query, session)
    result.translate()
    return result