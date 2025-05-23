from classes.example_classes import PhysicalObjectType

from sqlalchemy import Column, Enum, Float, ForeignKey, Integer, JSON, MetaData, String, Table
from sqlalchemy.orm import RelationshipProperty, registry, relationship
import classes.example_classes

metadata = MetaData()


t_DoublePositionAggregator = Table(
    'DoublePositionAggregator', metadata,
    Column('id', Integer, primary_key=True)
)

t_EnumContainer = Table(
    'EnumContainer', metadata,
    Column('id', Integer, primary_key=True),
    Column('value', Enum(classes.example_classes.ValueEnum), nullable=False)
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
    Column('id', Integer, primary_key=True),
    Column('some_strings', JSON)
)

t_Position = Table(
    'Position', metadata,
    Column('id', Integer, primary_key=True),
    Column('x', Float, nullable=False),
    Column('y', Float, nullable=False),
    Column('z', Float, nullable=False),
    Column('positions_positions_id', ForeignKey('Positions.id')),
    Column('doublepositionaggregator_positions1_id', ForeignKey('DoublePositionAggregator.id')),
    Column('doublepositionaggregator_positions2_id', ForeignKey('DoublePositionAggregator.id')),
    Column('polymorphic_type', String)
)

t_Pose = Table(
    'Pose', metadata,
    Column('id', Integer, primary_key=True),
    Column('position_id', ForeignKey('Position.id'), nullable=False),
    Column('orientation_id', ForeignKey('Orientation.id'), nullable=False)
)

t_Position4D = Table(
    'Position4D', metadata,
    Column('id', ForeignKey('Position.id'), primary_key=True),
    Column('w', Float, nullable=False)
)

t_SimulatedObject = Table(
    'SimulatedObject', metadata,
    Column('id', Integer, primary_key=True),
    Column('concept', PhysicalObjectType, nullable=False),
    Column('pose_id', ForeignKey('Pose.id'), nullable=False)
)

mapper_registry = registry(metadata=metadata)

m_Position = mapper_registry.map_imperatively(classes.example_classes.Position, t_Position, polymorphic_on = "polymorphic_type", polymorphic_identity = "Position")

m_Orientation = mapper_registry.map_imperatively(classes.example_classes.Orientation, t_Orientation, )

m_Pose = mapper_registry.map_imperatively(classes.example_classes.Pose, t_Pose, properties = dict(position=relationship('Position',foreign_keys=[t_Pose.c.position_id]), 
orientation=relationship('Orientation',foreign_keys=[t_Pose.c.orientation_id])))

m_Positions = mapper_registry.map_imperatively(classes.example_classes.Positions, t_Positions, properties = dict(positions=relationship('Position',foreign_keys=[t_Position.c.positions_positions_id])))

m_EnumContainer = mapper_registry.map_imperatively(classes.example_classes.EnumContainer, t_EnumContainer, )

m_Node = mapper_registry.map_imperatively(classes.example_classes.Node, t_Node, properties = dict(parent=relationship('Node',foreign_keys=[t_Node.c.parent_id])))

m_SimulatedObject = mapper_registry.map_imperatively(classes.example_classes.OriginalSimulatedObject, t_SimulatedObject, properties = dict(pose=relationship('Pose',foreign_keys=[t_SimulatedObject.c.pose_id]), 
concept=t_SimulatedObject.c.concept))

m_DoublePositionAggregator = mapper_registry.map_imperatively(classes.example_classes.DoublePositionAggregator, t_DoublePositionAggregator, properties = dict(positions1=relationship('Position',foreign_keys=[t_Position.c.doublepositionaggregator_positions1_id]), 
positions2=relationship('Position',foreign_keys=[t_Position.c.doublepositionaggregator_positions2_id])))

m_Position4D = mapper_registry.map_imperatively(classes.example_classes.Position4D, t_Position4D, polymorphic_identity = "Position4D", inherits = m_Position)
