from rosidl_parser.definition import Annotation
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from classes.example_classes import *

from orm_interface import *

engine = create_engine('sqlite:///:memory:', echo=False)
session = Session(engine)
mapper_registry.metadata.create_all(engine)

p1 = Pose(position=Position(x=1, y=2, z=3), orientation=Orientation(x=1, y=2, z=3, w=4))
e1 = EnumContainer(ValueEnum.A)
dp1 = DoublePositionAggregator([p1.position], [p1.position])

obj1 = OriginalSimulatedObject(
    concept = Cup(),
    pose = p1,
    placeholder=3.14
)
annotated_obj = ObjectAnnotation(obj1)


session.add(p1)
session.add(e1)
session.add(dp1)
session.add(annotated_obj)
session.commit()

queried_p1 = session.scalars(select(Pose)).one()
print(queried_p1)
e1 = session.scalars(select(EnumContainer)).one()
print(type(e1.value))
dp1 = session.scalars(select(DoublePositionAggregator)).one()
print(dp1)

anno1 = session.scalars(select(OriginalSimulatedObject)).first()
print(anno1)

print(session.scalars(select(ObjectAnnotation)).first())