import ormatic.example
from sqlalchemy.orm import registry, relationship 
from sqlalchemy import Column, Float, ForeignKey, Integer, MetaData, String, Table

metadata = MetaData()


t_Orientation = Table(
    'Orientation', metadata,
    Column('id', Integer, primary_key=True),
    Column('x', Float),
    Column('y', Float),
    Column('z', Float),
    Column('w', Float)
)

t_Positions = Table(
    'Positions', metadata,
    Column('id', Integer, primary_key=True)
)

t_Position = Table(
    'Position', metadata,
    Column('id', Integer, primary_key=True),
    Column('x', Float),
    Column('y', Float),
    Column('z', Float),
    Column('positions_id', ForeignKey('Positions.id')),
    Column('polymorphic_type', String)
)

t_Pose = Table(
    'Pose', metadata,
    Column('id', Integer, primary_key=True),
    Column('position_id', ForeignKey('Position.id')),
    Column('orientation_id', ForeignKey('Orientation.id'))
)

t_Position4D = Table(
    'Position4D', metadata,
    Column('id', ForeignKey('Position.id'), primary_key=True),
    Column('w', Float)
)

mapper_registry = registry(metadata=metadata)

m_Position = mapper_registry.map_imperatively(ormatic.example.Position, t_Position, polymorphic_on = "polymorphic_type", polymorphic_identity = "Position")

m_Orientation = mapper_registry.map_imperatively(ormatic.example.Orientation, t_Orientation, )

m_Pose = mapper_registry.map_imperatively(ormatic.example.Pose, t_Pose, properties = dict(position=relationship("Position"), 
orientation=relationship("Orientation")))

m_Position4D = mapper_registry.map_imperatively(ormatic.example.Position4D, t_Position4D, polymorphic_identity = "Position4D", inherits = m_Position)

m_Positions = mapper_registry.map_imperatively(ormatic.example.Positions, t_Positions, properties = dict(positions=relationship("Position", default_factory=list)))
