from __future__ import annotations

from typing import Dict, List, Tuple, Any, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import aliased

from entity_query_language.symbolic import (
    SymbolicExpression,
    Variable,
    Attribute,
    Comparator,
    AND,
    OR,
    LogicalOperator,
)

from .dao import get_dao_class, NoDAOFoundError


class EQLTranslationError(Exception):
    """Raised when an EQL expression cannot be translated into SQLAlchemy."""


def eql_to_sqlalchemy(expr: SymbolicExpression):
    """
    Translate an entity_query_language SymbolicExpression into a SQLAlchemy selectable.

    - Variables referring to domain classes are replaced by their DAO variants
      (using ormatic.dao.get_dao_class).
    - Produces a SQLAlchemy select() with appropriate WHERE conditions.

    Notes/Limitations:
    - Initial support focuses on simple attribute comparisons and logical AND/OR.
    - Attribute chains that traverse relationships beyond a single table may
      require explicit joins which are not yet auto-inserted here.

    :param expr: The EQL SymbolicExpression to translate.
    :return: A SQLAlchemy Select object.
    :raises NoDAOFoundError: If a variable class has no DAO mapping.
    :raises EQLTranslationError: If the expression contains unsupported constructs.
    """

    # 1) Collect variables and map to DAO classes; create an alias per variable
    var_instances: List[Variable] = [v for v in getattr(expr, "all_leaf_instances_", []) if isinstance(v, Variable)]

    # Keep only variables that represent entities (i.e., that have a DAO); constants will not have DAOs
    var_entity_instances: List[Variable] = []
    alias_map: Dict[int, Any] = {}

    for v in var_instances:
        dao_cls = get_dao_class(v.cls_) if v.cls_ is not None else None
        if dao_cls is not None:
            var_entity_instances.append(v)
            alias_map[v.id_] = aliased(dao_cls)

    if not alias_map:
        # Nothing to select from; expression doesn't reference any known entity
        raise EQLTranslationError("No entity variables with DAO mappings were found in the expression.")

    # 2) Build the WHERE condition by recursively translating the expression
    where_clause = _to_sql_condition(expr, alias_map)

    # 3) Build select list (one selectable per variable-entity alias, stable order)
    # Use the order of first appearance of variable instances
    selectables = [alias_map[v.id_] for v in var_entity_instances if v.id_ in alias_map]

    stmt = select(*selectables)
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    return stmt


def _to_sql_condition(expr: SymbolicExpression, alias_map: Dict[int, Any]):
    """Translate an EQL expression into a SQLAlchemy boolean condition."""
    if isinstance(expr, Comparator):
        left = _operand_to_sql(expr.left_, alias_map)
        right = _operand_to_sql(expr.right_, alias_map)

        op = expr.operation_
        if op == "==":
            return left == right
        elif op == "!=":
            return left != right
        elif op == ">":
            return left > right
        elif op == ">=":
            return left >= right
        elif op == "<":
            return left < right
        elif op == "<=":
            return left <= right
        elif op == "in":
            # Right-hand side can be a list/iterable or a selectable/expression
            if isinstance(right, (list, tuple, set)):
                return left.in_(list(right))
            return left.in_(right)
        else:
            raise EQLTranslationError(f"Unsupported comparator operation: {op}")

    if isinstance(expr, AND):
        left = _to_sql_condition(expr.left_, alias_map)
        right = _to_sql_condition(expr.right_, alias_map)
        if left is None:
            return right
        if right is None:
            return left
        return and_(left, right)

    if isinstance(expr, OR):
        left = _to_sql_condition(expr.left_, alias_map)
        right = _to_sql_condition(expr.right_, alias_map)
        if left is None:
            return right
        if right is None:
            return left
        return or_(left, right)

    if isinstance(expr, LogicalOperator):
        # Other logical forms not explicitly handled
        raise EQLTranslationError(f"Unsupported logical operator: {type(expr).__name__}")

    # Fallback: if it's a bare Attribute/Variable used as a truthy check, unsupported
    return None


def _operand_to_sql(operand: SymbolicExpression, alias_map: Dict[int, Any]):
    """
    Convert an operand (Attribute, Variable, or literal-wrapped Variable) to a SQLAlchemy expression or Python value.
    - For Attribute chains: resolve to alias.column.
    - For Variables with DAOs: return the table alias itself (rare in comparisons).
    - For literal Variables (constants): return the literal Python value.
    """
    # Attribute chain
    if isinstance(operand, Attribute):
        base_alias, attr_chain = _resolve_attribute_chain(operand, alias_map)
        # Traverse the chain on the SQLAlchemy alias
        current = base_alias
        for name in attr_chain:
            try:
                current = getattr(current, name)
            except AttributeError as e:
                raise EQLTranslationError(f"Unknown attribute '{name}' on {current}") from e
        return current

    # Variable
    if isinstance(operand, Variable):
        # If variable corresponds to an entity, return its alias
        if operand.id_ in alias_map:
            return alias_map[operand.id_]
        # Otherwise, it's likely a literal (wrapped) value
        const = _variable_to_constant(operand)
        return const

    # Unsupported operand type
    raise EQLTranslationError(f"Unsupported operand type: {type(operand).__name__}")


def _variable_to_constant(var: Variable):
    """Extract the Python literal from a Variable that represents a constant domain of one element."""
    domain = getattr(var, "domain_", None)
    if domain is None:
        # If it has a cls_ and no DAO mapping, still attempt to instantiate? Prefer not.
        raise EQLTranslationError("Variable without domain cannot be used as a literal.")
    # The domain is a HashedIterable; attempt to get first (they store by id/index)
    try:
        # Iterate to fetch first
        for hv in domain:
            return hv.value if hasattr(hv, "value") else hv
    except Exception:
        pass
    # Some domains may be plain iterables
    try:
        return next(iter(domain))
    except Exception as e:
        raise EQLTranslationError("Unable to extract literal value from variable domain.") from e


def _resolve_attribute_chain(attr: Attribute, alias_map: Dict[int, Any]) -> Tuple[Any, List[str]]:
    """
    Given an Attribute DomainMapping, return (base_alias, [attr,...]) where base_alias is the
    SQLAlchemy alias for the underlying Variable and the attr list is the chain of attribute names.
    """
    chain: List[str] = []
    current = attr
    # Walk down to the base Variable, collecting attribute names from outside to inside
    while isinstance(current, Attribute):
        chain.insert(0, current.attr_name_)
        current = current.child_

    if not isinstance(current, Variable):
        raise EQLTranslationError("Attribute chain does not terminate at a Variable.")

    base_var: Variable = current
    if base_var.id_ not in alias_map:
        raise NoDAOFoundError(base_var.cls_)

    base_alias = alias_map[base_var.id_]
    return base_alias, chain
