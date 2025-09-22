from __future__ import annotations

from dataclasses import dataclass
from typing import List, Any, Optional
import operator

import sqlalchemy.inspection
from sqlalchemy import and_, or_, select, Select, func, literal, not_ as sa_not
from sqlalchemy.orm import Session

from entity_query_language.symbolic import (
    SymbolicExpression,
    Attribute,
    Comparator,
    AND,
    OR,
    An,
    The,
    Variable,
    Literal,
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
    # Tracks joins introduced while traversing attribute chains (by path)
    _joined_daos: set[Any] = None
    # Tracks joins of whole DAO classes introduced due to variable equality joins
    _joined_tables: set[type] = None

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
        dao_class = get_dao_class(self.select_like.selected_variable._type_)
        self.sql_query = select(dao_class)
        # initialize join caches
        self._joined_daos = set()
        self._joined_tables = set()
        conditions = self.translate_query(self.root_condition)
        if conditions is not None:
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
        Supports binary AND nodes (left/right) introduced in newer EQL.
        :param query: EQL query
        :return: SQL expression or None if all parts are handled via JOINs.
        """
        parts = []
        # New API: binary tree with left/right
        if hasattr(query, "left") and hasattr(query, "right"):
            left_part = self.translate_query(query.left)
            right_part = self.translate_query(query.right)
            if left_part is not None:
                parts.append(left_part)
            if right_part is not None:
                parts.append(right_part)
        else:
            # Backward compatibility: list of children
            children = getattr(query, "_children_", None) or []
            for c in children:
                p = self.translate_query(c)
                if p is not None:
                    parts.append(p)
        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        return and_(*parts)

    def translate_or(self, query: OR):
        """
        Translate an eql.OR query into an sql.OR.
        Supports binary OR nodes (left/right) introduced in newer EQL.
        :param query: EQL query
        :return: SQL expression or None if all parts are handled via JOINs.
        """
        parts = []
        if hasattr(query, "left") and hasattr(query, "right"):
            left_part = self.translate_query(query.left)
            right_part = self.translate_query(query.right)
            if left_part is not None:
                parts.append(left_part)
            if right_part is not None:
                parts.append(right_part)
        else:
            children = getattr(query, "_children_", None) or []
            for c in children:
                p = self.translate_query(c)
                if p is not None:
                    parts.append(p)
        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        return or_(*parts)

    def translate_comparator(self, query: Comparator):
        """
        Translate an eql.Comparator query into a SQLAlchemy binary expression, or perform JOINs for
        equality between attributes of different symbolic variables.
        Supports ==, !=, <, <=, >, >=, and 'in'.
        """
        # Helper: extract underlying Variable and its python type from a leaf-like node
        def _extract_var_and_type(node: Any):
            # direct variable
            if isinstance(node, Variable):
                return node, getattr(node, "_type_", None)
            # An/The/Entity wrappers often expose the variable via _var_
            var = getattr(node, "_var_", None)
            if isinstance(var, Variable):
                return var, getattr(var, "_type_", None)
            # Fallbacks
            t = getattr(node, "_type_", None)
            return None, t

        # Special-case: equality between attributes of two different variables -> JOIN with ON clause
        if (
            (
                getattr(query.operation, "__name__", None) == "eq"
                or query.operation is operator.eq
            )
            and isinstance(query.left, Attribute)
            and isinstance(query.right, Attribute)
        ):
            # Extract leaf variables and base DAOs
            def leaf_variable(attr: Attribute):
                node = attr
                while isinstance(node, Attribute):
                    node = getattr(node, "_child_", None)
                var, _ = _extract_var_and_type(node)
                return var or node

            def base_dao_of(attr: Attribute):
                node = attr
                while isinstance(node, Attribute):
                    node = getattr(node, "_child_", None)
                _, t = _extract_var_and_type(node)
                return get_dao_class(t) if t is not None else None

            left_leaf = leaf_variable(query.left)
            right_leaf = leaf_variable(query.right)
            left_dao = base_dao_of(query.left)
            right_dao = base_dao_of(query.right)

            # Only apply if leaves (variables) differ
            if (
                left_leaf is not right_leaf
                and left_dao is not None
                and right_dao is not None
            ):
                # Determine if last attribute on both sides are relationships and obtain their local FK columns
                def rel_and_fk(dao_cls, attr_name):
                    mapper = sqlalchemy.inspection.inspect(dao_cls)
                    rel = (
                        mapper.relationships.get(attr_name)
                        if hasattr(mapper.relationships, "get")
                        else None
                    )
                    if rel is None:
                        for r in mapper.relationships:
                            if r.key == attr_name:
                                rel = r
                                break
                    if rel is None:
                        return None, None
                    # choose first local column key (assumes single-column FK)
                    col = next(iter(rel.local_columns))
                    fk_col = getattr(dao_cls, col.key)
                    return rel, fk_col

                # Find the immediate attribute names accessed on each variable
                left_attr_name = query.left._attr_name_
                right_attr_name = query.right._attr_name_

                left_rel, left_fk = rel_and_fk(left_dao, left_attr_name)
                right_rel, right_fk = rel_and_fk(right_dao, right_attr_name)

                if left_rel is not None and right_rel is not None:
                    # Build JOIN to the non-anchor DAO with ON clause being the equality condition
                    anchor_dao = get_dao_class(
                        self.select_like.selected_variable._type_
                    )
                    if anchor_dao is None:
                        raise EQLTranslationError("Selected variable has no DAO class")

                    # Decide which side to join (the one that is not the anchor)
                    if left_dao is anchor_dao:
                        target_dao, target_fk, anchor_fk = right_dao, right_fk, left_fk
                    else:
                        target_dao, target_fk, anchor_fk = left_dao, left_fk, right_fk

                    if self._joined_tables is None:
                        self._joined_tables = set()

                    if target_dao not in self._joined_tables:
                        onclause = target_fk == anchor_fk
                        self.sql_query = self.sql_query.join(
                            target_dao, onclause=onclause
                        )
                        self._joined_tables.add(target_dao)
                    # handled via JOIN; no WHERE part for this comparator
                    return None

        # Fallback: evaluate both sides as SQL expressions/values
        def to_sql_side(side):
            # Attribute -> resolved SQLA column (with joins if needed)
            if isinstance(side, Attribute):
                return self.translate_attribute(side)
            # EQL Variable/literal with domain
            if isinstance(side, (Variable, Literal)):
                return self._literal_from_variable_domain(side)
            # Plain Python literal or iterable
            return side

        left = to_sql_side(query.left)
        right = to_sql_side(query.right)

        op = query.operation
        # Map callable operations to SQLAlchemy expressions
        if op is operator.eq or getattr(op, "__name__", None) == "eq":
            return left == right
        if op is operator.gt or getattr(op, "__name__", None) == "gt":
            return left > right
        if op is operator.lt or getattr(op, "__name__", None) == "lt":
            return left < right
        if op is operator.ge or getattr(op, "__name__", None) == "ge":
            return left >= right
        if op is operator.le or getattr(op, "__name__", None) == "le":
            return left <= right
        if op is operator.ne or getattr(op, "__name__", None) == "ne":
            return left != right
        # contains(a, b): for general iterables means b in a; for strings means substring containment
        name = getattr(op, "__name__", "")
        if op is operator.contains or name in ("contains", "not_contains", "in_"):
            is_not = name == "not_contains"

            # Special-case: in_ semantics produced as contains(Literal(collection), Attribute(column)) by EQL
            if name in ("contains", "in_") and isinstance(query.left, Literal) and isinstance(query.right, Attribute):
                try:
                    values = [hv.value for hv in query.left._domain_]
                except Exception:
                    # fallback to single literal value
                    values = [getattr(query.left, "value", None)]
                # If it's clearly a collection (multiple values) or a single non-string, treat as membership
                if len(values) != 1 or (values and not isinstance(values[0], str)):
                    col = self.translate_attribute(query.right)
                    expr = col.in_(values)
                    return sa_not(expr) if is_not else expr
                # else fall through to string containment handling below

            # 1) Collection membership cases for plain Python iterables
            if isinstance(left, (list, tuple, set)):
                expr = right.in_(left)
            elif isinstance(right, (list, tuple, set)):
                expr = left.in_(right)
            # 2) String containment cases
            elif isinstance(left, str) and not isinstance(right, str):
                # haystack is literal string, needle is a column/expression
                expr = func.instr(literal(left), right) > 0
            elif not isinstance(left, str) and isinstance(right, str):
                # haystack is column/expression, needle is literal string
                try:
                    expr = left.contains(right)
                except AttributeError:
                    expr = left.like("%" + right + "%")
            elif isinstance(left, str) and isinstance(right, str):
                # both literals -> constant truth value
                expr = literal(right in left)
            else:
                # both are SQL expressions/columns
                expr = func.instr(left, right) > 0
            return sa_not(expr) if is_not else expr
        raise EQLTranslationError(f"Unknown operator: {query.operation}")

    def _literal_from_variable_domain(self, var_like: Any) -> Any:
        """
        Extract a representative Python value from an EQL Variable/Literal domain for use in SQL comparisons.
        - If it's an EQL Literal, return the literal value directly.
        - If it's an EQL Variable with a domain of mapped entities, try to resolve to the corresponding DAO id.
          Otherwise, return the sample value as-is (numbers/strings/etc.).
        """
        try:
            sample = next(iter(var_like._domain_)).value
        except Exception:
            # No domain or unexpected structure; just return as-is
            return getattr(var_like, "value", var_like)

        # If it's an explicit EQL Literal, return raw python value.
        if isinstance(var_like, Literal):
            return sample

        # If the sample corresponds to a mapped entity, try to map to DAO id
        from .dao import get_dao_class

        dao_class = get_dao_class(type(sample))
        if dao_class is None:
            return sample

        # If it's already a DAO instance
        if isinstance(sample, dao_class):
            return getattr(sample, "id", sample)

        # Try to resolve DAO instance by a simple unique attribute if available
        filters = {}
        if hasattr(sample, "id_"):
            filters["id_"] = getattr(sample, "id_")
        elif hasattr(sample, "name"):
            filters["name"] = getattr(sample, "name")

        if filters:
            dao_instance = self.session.query(dao_class).filter_by(**filters).first()
            if dao_instance is not None:
                return getattr(dao_instance, "id", dao_instance)

        # Fallback
        return sample

    def _get_entity_filter(self, entity) -> dict:
        """Get filter criteria to find the DAO instance for an entity."""
        # This is a simple implementation that works for entities with a 'name' attribute
        if hasattr(entity, "name"):
            return {"name": entity.name}
        # Add more sophisticated matching logic as needed
        return {}

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
            node = getattr(node, "_child_", None)

        # Resolve the base python class of the variable at the leaf of the chain
        base_cls = getattr(node, "_type_", None)
        if base_cls is None:
            var = getattr(node, "_var_", None)
            if var is not None:
                base_cls = getattr(var, "_type_", None)
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
            rel = (
                mapper.relationships.get(name)
                if hasattr(mapper.relationships, "get")
                else None
            )
            if rel is None:
                # check by iterating if .get not available
                for r in mapper.relationships:
                    if r.key == name:
                        rel = r
                        break
            if rel is not None:
                # If this is the last element in the chain, return the FK column instead of joining
                if idx == len(names) - 1:
                    # Return the foreign key column that backs this relationship
                    # Get the first local column (assumes single-column FK)
                    local_col = next(iter(rel.local_columns))
                    return getattr(current_dao, local_col.key)
                else:
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
                    f"Attribute '{name}' on {current_dao.__name__} is not a relationship but chain continues."
                )
            try:
                return getattr(current_dao, name)
            except AttributeError as e:
                raise EQLTranslationError(
                    f"Column '{name}' not found on {current_dao.__name__}."
                ) from e

        # If we get here, the loop completed without returning, which shouldn't happen with the new logic
        raise EQLTranslationError("Attribute chain processing error.")


def eql_to_sql(query: SymbolicExpression, session: Session):
    result = EQLTranslator(query, session)
    result.translate()
    return result
