from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from ormatic.example import *
from orm_interface import *

engine = create_engine('sqlite:///:memory:')
session = Session(engine)
mapper_registry.metadata.create_all(engine)


p1 = Pose(position=Position(x=1, y=2, z=3), orientation=Orientation(x=1, y=2, z=3, w=4))
e1 = EnumContainer(ValueEnum.A)


session.add(p1)
session.add(e1)
session.commit()

queried_p1 = session.scalars(select(Pose)).one()
print(queried_p1)
e1 = session.scalars(select(EnumContainer)).one()
print(type(e1.value))