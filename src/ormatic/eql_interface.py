from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional

from sqlalchemy import and_, or_, select, inspect, Select
from sqlalchemy.orm import aliased, RelationshipProperty, Session

from entity_query_language.symbolic import (
    SymbolicExpression,
    Variable,
    Attribute,
    Comparator,
    AND,
    OR,
    LogicalOperator, An, The
)

from .dao import get_dao_class, NoDAOFoundError


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

        sql_query = select(dao_class)

        conditions = translate_query(self.root_condition)
        self.sql_query = sql_query.where(conditions)

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

def eql_to_sql(query: SymbolicExpression, session: Session):
    result = EQLTranslator(query, session)
    result.translate()
    return result

def translate_query(query: SymbolicExpression):
    if isinstance(query, AND):
        return translate_and(query)
    elif isinstance(query, OR):
        return translate_or(query)
    elif isinstance(query, Comparator):
        return translate_comparator(query)
    elif isinstance(query, Attribute):
        return translate_attribute(query)
    else:
        raise EQLTranslationError(f"Unknown query type: {type(query)}")


def translate_and(query: AND):
    """
    Translate an eql.AND query into an sql.AND.
    :param query: EQL query
    :return: SQL query
    """
    return and_(*[translate_query(c) for c in query._children_])

def translate_or(query: OR):
    """
    Translate an eql.OR query into an sql.OR.
    :param query: EQL query
    :return: SQL query
    """
    return or_(*[translate_query(c) for c in query._children_])

def translate_comparator(query: Comparator):
    """
    Translate an eql.Comparator query into an sql.Comparator.
    :param query: EQL query
    :return: SQL query
    """
    left = translate_attribute(query.left) if isinstance(query.left, Attribute) else next(iter(query.left._domain_)).value
    right = translate_attribute(query.right) if isinstance(query.right, Attribute) else next(iter(query.right._domain_)).value

    # Apply the comparison operator
    if query.operation == '==':
        return left == right
    elif query.operation == '>':
        return left > right
    elif query.operation == '<':
        return left < right
    elif query.operation == '>=':
        return left >= right
    elif query.operation == '<=':
        return left <= right
    elif query.operation == '!=':
        return left != right
    else:
        raise EQLTranslationError(f"Unknown operator: {query.operation}")

def translate_attribute(query: Attribute):
    """
    Translate an eql.Attribute query into an sql.Attribute.
    :param query: EQL query
    :return: SQL query
    """
    cls = query._child_._cls_
    print(cls)
    dao_class = get_dao_class(cls)
    column = getattr(dao_class, query._attr_name_)
    return column
