# Welcome to ORMatic

ORMatic is a python package that automatically converts python dataclasses to sqlalchemy tables.
This is done using the [imperative mapping](https://docs.sqlalchemy.org/en/20/orm/mapping_styles.html#imperative-mapping).

When designing the dataclasses there are a couple of rules that need to be followed:
- Fields that are not mapped start with an `_` (underscore).
- The only allowed union is the `Optional[_T]` union. Whenever you want a union of other types, use inheritance instead.
- Iterables are never optional and never nested. 
If you want an optional iterable, use an empty iterable instead.

Features (TODO):
- Write table definitions to a file such that on import the tables are mapped with the classes.
- Inheritance using Joint Table Inheritance.
- Support for enums.
- Support for many-many relationships.
- 