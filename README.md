# Welcome to ORMatic

ORMatic is a python package that automatically converts python dataclasses to sqlalchemy tables.
This is done using the [imperative mapping](https://docs.sqlalchemy.org/en/20/orm/mapping_styles.html#imperative-mapping).

When designing the dataclasses there are a couple of rules that need to be followed:
- Fields that are not mapped start with an `_` (underscore).
- The only allowed union is the `Optional[_T]` union. Whenever you want a union of other types, use inheritance instead.
- Iterables are never optional and never nested. 
If you want an optional iterable, use an empty iterable as default factory instead.
- No multiple inheritance.
- No forward referenced classes.

Features:
- Automatic conversion of dataclasses to sqlalchemy tables.
- Automatic application of relationships.
- Automatic generation of ORM interface.
- ORM interface only affects your code if it is imported.

- Support for inheritance.
- Support for optional fields.
- Support for nested dataclasses.
- Support for many-many relationships.
- Support for self-referencing relationships.

## Example

The most common use case is to create an ORM for an existing set of dataclasses.
An example for such a set of dataclasses is found in 
[example.py](https://github.com/tomsch420/ormatic/blob/master/src/ormatic/example.py).
The automatically generated ORM interface is found in [orm_interface.py](https://github.com/tomsch420/ormatic/blob/master/test/orm_interface.py).
Example usage of the ORM interface is found in [integration.py](https://github.com/tomsch420/ormatic/blob/master/test/integration.py).

The following script generates the bindings in [orm_interface.py](https://github.com/tomsch420/ormatic/blob/master/test/orm_interface.py).

```python
import sqlacodegen.generators
from sqlalchemy import create_engine
from sqlalchemy.orm import registry, Session

from example import *
from ormatic.ormatic import ORMatic


def main():
    mapper_registry = registry()

    engine = create_engine('sqlite:///:memory:')

    classes = [Position, Orientation, Pose, Position4D, Positions, EnumContainer, Node]
    ormatic = ORMatic(classes, mapper_registry)
    ormatic.make_all_tables()
    mapper_registry.metadata.create_all(engine)

    generator = sqlacodegen.generators.TablesGenerator(mapper_registry.metadata, engine, [])

    with open('orm_interface.py', 'w') as f:
        ormatic.to_python_file(generator, f)


if __name__ == '__main__':
    main()

```
