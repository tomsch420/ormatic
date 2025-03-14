# Welcome to ORMatic

ORMatic is a python package that automatically converts python dataclasses to sqlalchemy tables.
This is done using the [imperative mapping](https://docs.sqlalchemy.org/en/20/orm/mapping_styles.html#imperative-mapping).

When designing the dataclasses there are a couple of rules that need to be followed:
- Fields that are not mapped start with an `_` (underscore).
- The only allowed union is the `Optional[_T]` union. Whenever you want a union of other types, use inheritance instead.
- Iterables are never optional and never nested. 
If you want an optional iterable, use an empty iterable as default factory instead.
- No multiple inheritance.

Features:
- Automatic conversion of dataclasses to sqlalchemy tables.
- Automatic application of relationships.
- Automatic generation of ORM interface.
- ORM interface only affects your code if it is imported.

- Support for inheritance.
- Support for optional fields.
- Support for nested dataclasses.
- Support for many-many relationships (TODO).

## Example

The most common use case is to create an ORM for an existing set of dataclasses.
An example for such a set of dataclasses is found in 
[example.py](https://github.com/tomsch420/ormatic/blob/master/src/ormatic/example.py).
The automatically generated ORM interface is found in [orm_interface.py](https://github.com/tomsch420/ormatic/blob/master/test/orm_interface.py).
Example usage of the ORM interface is found in [integration.py](https://github.com/tomsch420/ormatic/blob/master/test/integration.py).

