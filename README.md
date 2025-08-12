# Welcome to ORMatic

ORMatic is a python package that automatically converts python dataclasses to sqlalchemy tables.
This is done using the [declarative mapping](https://docs.sqlalchemy.org/en/20/orm/mapping_styles.html#declarative-mapping).
The package outputs a file that can be used as an [SQLAlchemy](https://www.sqlalchemy.org/) interface. 

When designing the dataclasses that should be mapped there are a couple of rules that need to be followed:
- Fields that are not mapped start with an `_` (underscore).
- The only allowed union is the `Optional[_T]` union. Whenever you want a union of other types, use common 
superclasses as type instead.
- Iterables are never optional and never nested. 
If you want an optional iterable, use an empty iterable as default factory instead.
- Superclasses that are not the first mentioned superclass are not queryable via abstract queries. (Polymorphic identity)  

If your dataclasses are not compatible with this pattern, there are two workarounds,
the Alternative Mapping and the Type Decorator.

## Features:

- Automatic conversion of dataclasses to sqlalchemy tables.
- Automatic application of relationships.
- Automatic generation of ORM interface.
- ORM interface never affects your existing code.

- Support for inheritance.
- Support for optional fields.
- Support for nested dataclasses.
- Support for many-many relationships.
- Support for self-referencing relationships.

## Example

The most common use case is to create an ORM for an existing set of dataclasses.
An example for such a set of dataclasses is found in 
[example.py](https://github.com/tomsch420/ormatic/blob/master/test/classes/example_classes.py).
The automatically generated ORM interface is found in [sqlalchemy_interface.py](https://github.com/tomsch420/ormatic/blob/master/test/classes/sqlalchemy_interface.py).
Example usage of the ORM interface is found in [integration.py](https://github.com/tomsch420/ormatic/blob/master/test/integration.py).

The following script generates the bindings in [sqlalchemy_interface.py](https://github.com/tomsch420/ormatic/blob/master/test/classes/sqlalchemy_interface.py).
```python
from enum import Enum
import test.classes.example_classes
from ormatic.ormatic import ORMatic
from ormatic.dao import AlternativeMapping
from ormatic.utils import recursive_subclasses, classes_of_module
from dataclasses import is_dataclass


def main():
    
    # get classes that should be mapped
    classes = set(recursive_subclasses(AlternativeMapping))
    classes |= set(classes_of_module(test.classes.example_classes))
    
    # remove classes that should not be mapped
    classes -= set(recursive_subclasses(Enum))
    classes -= set([cls for cls in classes if not is_dataclass(cls)])
    
    ormatic = ORMatic(classes)
    ormatic.make_all_tables()

    with open('orm_interface.py', 'w') as f:
        ormatic.to_sqlalchemy_file(f)

        
if __name__ == '__main__':
    main()

```

# TODO List
- ~~Nothing~~

## Using Entity Query Language with ORMatic (EQL → SQLAlchemy)

You can express queries using the entity_query_language library and translate them into SQLAlchemy statements with ormatic.

Example using the sample classes from test/classes and the generated SQLAlchemy interface:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, configure_mappers

from entity_query_language.entity import let
from entity_query_language.symbolic import Or, in_

from classes.example_classes import Position
from classes.sqlalchemy_interface import Base, PositionDAO

from ormatic.eql_interface import eql_to_sqlalchemy

# Initialize in-memory DB
configure_mappers()
engine = create_engine('sqlite:///:memory:')
session = Session(engine)
Base.metadata.create_all(engine)

# Insert sample data
session.add_all([
    PositionDAO.to_dao(Position(1, 2, 3)),
    PositionDAO.to_dao(Position(1, 2, 4)),
    PositionDAO.to_dao(Position(2, 9, 10)),
])
session.commit()

# Build an EQL expression
position = let(type_=Position, domain=[Position(0, 0, 0)])  # domain content is irrelevant for translation
expr = position.z > 3  # simple comparator

# Translate to SQLAlchemy and execute
stmt = eql_to_sqlalchemy(expr)
rows = session.scalars(stmt).all()  # → PositionDAO rows with z > 3

# More complex logic
expr2 = Or(position.z == 4, position.x == 2)
stmt2 = eql_to_sqlalchemy(expr2)
rows2 = session.scalars(stmt2).all()  # rows where z == 4 OR x == 2

# Using "in" operator
expr3 = in_(position.x, [1, 7])
stmt3 = eql_to_sqlalchemy(expr3)
rows3 = session.scalars(stmt3).all()  # rows where x ∈ {1, 7}
```

Notes:
- The translator maps EQL Variables to the corresponding DAO classes (via ormatic.dao.get_dao_class) and produces a SQLAlchemy select(...) with a WHERE clause.
- It currently focuses on direct attribute comparisons on a single table and supports ==, !=, >, >=, <, <=, and in, as well as logical AND/OR.
