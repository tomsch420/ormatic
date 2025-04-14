from sqlalchemy import Column, Enum, Float, ForeignKey, Integer, MetaData, String, Table
from sqlalchemy.orm import registry, relationship
import ormatic.example

metadata = MetaData()


t_EnumContainer = Table(
    'EnumContainer', metadata,
    Column('id', Integer, primary_key=True),
    Column('value', Enum(ormatic.example.ValueEnum), nullable=False)
)

t_Node = Table(
    'Node', metadata,
    Column('id', Integer, primary_key=True),
    Column('parent_id', ForeignKey('Node.id'))
)

t_Orientation = Table(
    'Orientation', metadata,
    Column('id', Integer, primary_key=True),
    Column('x', Float, nullable=False),
    Column('y', Float, nullable=False),
    Column('z', Float, nullable=False),
    Column('w', Float)
)

t_Positions = Table(
    'Positions', metadata,
    Column('id', Integer, primary_key=True)
)

t_Position = Table(
    'Position', metadata,
    Column('id', Integer, primary_key=True),
    Column('x', Float, nullable=False),
    Column('y', Float, nullable=False),
    Column('z', Float, nullable=False),
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
    Column('w', Float, nullable=False)
)

mapper_registry = registry(metadata=metadata)

m_Position = mapper_registry.map_imperatively(ormatic.example.Position, t_Position, polymorphic_on = "polymorphic_type", polymorphic_identity = "Position")

m_Orientation = mapper_registry.map_imperatively(ormatic.example.Orientation, t_Orientation, )

m_Pose = mapper_registry.map_imperatively(ormatic.example.Pose, t_Pose, properties = dict(position=relationship("Position", foreign_keys=[t_Pose.c.position_id]), 
orientation=relationship("Orientation", foreign_keys=[t_Pose.c.orientation_id])))

m_Positions = mapper_registry.map_imperatively(ormatic.example.Positions, t_Positions, properties = dict(positions=relationship("Position", foreign_keys=[t_Positions.c.positions_id], default_factory=list)))

m_EnumContainer = mapper_registry.map_imperatively(ormatic.example.EnumContainer, t_EnumContainer, )

m_Node = mapper_registry.map_imperatively(ormatic.example.Node, t_Node, properties = dict(parent=relationship("Node", foreign_keys=[t_Node.c.parent_id], remote_side=[t_Node.c.id])))

m_Position4D = mapper_registry.map_imperatively(ormatic.example.Position4D, t_Position4D, polymorphic_identity = "Position4D", inherits = m_Position)
