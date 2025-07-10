from dataclasses import is_dataclass

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
- Fields that are typed as Sequence/Iterable should be stored as list
- Check deep inheritance
