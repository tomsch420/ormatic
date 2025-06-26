from classes.example_classes import PhysicalObjectType
from ormatic.custom_types import TypeType

from sqlalchemy import Boolean, Column, Enum, Float, ForeignKey, Integer, JSON, MetaData, String, Table
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

t_Molecule = Table(
    'Molecule', metadata,
    Column('id', Integer, primary_key=True),
    Column('ind1', Integer, nullable=False),
    Column('inda', Integer, nullable=False),
    Column('logp', Float, nullable=False),
    Column('lumo', Float, nullable=False),
    Column('mutagenic', Boolean, nullable=False)
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

t_Parent1 = Table(
    'Parent1', metadata,
    Column('id', Integer, primary_key=True),
    Column('obj', String(255), nullable=False),
    Column('polymorphic_type', String(255))
)

t_Parent2 = Table(
    'Parent2', metadata,
    Column('id', Integer, primary_key=True),
    Column('obj2', String(255), nullable=False)
)

t_Position4D = Table(
    'Position4D', metadata,
    Column('id', Integer, primary_key=True),
    Column('x', Float, nullable=False),
    Column('y', Float, nullable=False),
    Column('z', Float, nullable=False)
)

t_PositionTypeWrapper = Table(
    'PositionTypeWrapper', metadata,
    Column('id', Integer, primary_key=True),
    Column('position_type', TypeType)
)

t_Positions = Table(
    'Positions', metadata,
    Column('id', Integer, primary_key=True),
    Column('some_strings', JSON)
)

t_Atom = Table(
    'Atom', metadata,
    Column('id', Integer, primary_key=True),
    Column('element', Enum(classes.example_classes.Element), nullable=False),
    Column('type', Integer, nullable=False),
    Column('charge', Float, nullable=False),
    Column('molecule_atoms_id', ForeignKey('Molecule.id'))
)

t_MultipleInheritance = Table(
    'MultipleInheritance', metadata,
    Column('id', ForeignKey('Parent1.id'), primary_key=True),
    Column('obj2', String(255), nullable=False)
)

t_Position = Table(
    'Position', metadata,
    Column('id', Integer, primary_key=True),
    Column('x', Float, nullable=False),
    Column('y', Float, nullable=False),
    Column('z', Float, nullable=False),
    Column('doublepositionaggregator_positions1_id', ForeignKey('DoublePositionAggregator.id')),
    Column('doublepositionaggregator_positions2_id', ForeignKey('DoublePositionAggregator.id')),
    Column('positions_positions_id', ForeignKey('Positions.id')),
    Column('polymorphic_type', String(255))
)

t_Bond = Table(
    'Bond', metadata,
    Column('id', Integer, primary_key=True),
    Column('molecule_bonds_id', ForeignKey('Molecule.id')),
    Column('atom1_id', ForeignKey('Atom.id'), nullable=False),
    Column('atom2_id', ForeignKey('Atom.id'), nullable=False),
    Column('type', Integer, nullable=False)
)

t_Pose = Table(
    'Pose', metadata,
    Column('id', Integer, primary_key=True),
    Column('position_id', ForeignKey('Position.id'), nullable=False),
    Column('orientation_id', ForeignKey('Orientation.id'), nullable=False)
)

t_Position5D = Table(
    'Position5D', metadata,
    Column('id', ForeignKey('Position.id'), primary_key=True),
    Column('a', Float, nullable=False)
)

t_OGSimObjSubclass = Table(
    'OGSimObjSubclass', metadata,
    Column('id', Integer, primary_key=True),
    Column('concept', PhysicalObjectType, nullable=False),
    Column('pose_id', ForeignKey('Pose.id'), nullable=False)
)

t_OriginalSimulatedObject = Table(
    'OriginalSimulatedObject', metadata,
    Column('id', Integer, primary_key=True),
    Column('concept', PhysicalObjectType, nullable=False),
    Column('pose_id', ForeignKey('Pose.id'), nullable=False)
)

t_ObjectAnnotation = Table(
    'ObjectAnnotation', metadata,
    Column('id', Integer, primary_key=True),
    Column('object_reference_id', ForeignKey('OriginalSimulatedObject.id'), nullable=False)
)

mapper_registry = registry(metadata=metadata)

m_Atom = mapper_registry.map_imperatively(classes.example_classes.Atom, t_Atom, )

m_Position = mapper_registry.map_imperatively(classes.example_classes.Position, t_Position, polymorphic_on = "polymorphic_type", polymorphic_identity = "Position")

m_DoublePositionAggregator = mapper_registry.map_imperatively(classes.example_classes.DoublePositionAggregator, t_DoublePositionAggregator, properties = dict(positions1=relationship('Position',foreign_keys=[t_Position.c.doublepositionaggregator_positions1_id]), 
positions2=relationship('Position',foreign_keys=[t_Position.c.doublepositionaggregator_positions2_id])))

m_ObjectAnnotation = mapper_registry.map_imperatively(classes.example_classes.ObjectAnnotation, t_ObjectAnnotation, properties = dict(object_reference=relationship('OriginalSimulatedObject',foreign_keys=[t_ObjectAnnotation.c.object_reference_id])))

m_Node = mapper_registry.map_imperatively(classes.example_classes.Node, t_Node, properties = dict(parent=relationship('Node',foreign_keys=[t_Node.c.parent_id])))

m_OriginalSimulatedObject = mapper_registry.map_imperatively(classes.example_classes.OriginalSimulatedObject, t_OriginalSimulatedObject, properties = dict(pose=relationship('Pose',foreign_keys=[t_OriginalSimulatedObject.c.pose_id]), 
concept=t_OriginalSimulatedObject.c.concept))

m_Positions = mapper_registry.map_imperatively(classes.example_classes.Positions, t_Positions, properties = dict(positions=relationship('Position',foreign_keys=[t_Position.c.positions_positions_id])))

m_Pose = mapper_registry.map_imperatively(classes.example_classes.Pose, t_Pose, properties = dict(position=relationship('Position',foreign_keys=[t_Pose.c.position_id]), 
orientation=relationship('Orientation',foreign_keys=[t_Pose.c.orientation_id])))

m_EnumContainer = mapper_registry.map_imperatively(classes.example_classes.EnumContainer, t_EnumContainer, )

m_Orientation = mapper_registry.map_imperatively(classes.example_classes.Orientation, t_Orientation, )

m_Parent1 = mapper_registry.map_imperatively(classes.example_classes.Parent1, t_Parent1, polymorphic_on = "polymorphic_type", polymorphic_identity = "Parent1")

m_Parent2 = mapper_registry.map_imperatively(classes.example_classes.Parent2, t_Parent2, )

m_PositionTypeWrapper = mapper_registry.map_imperatively(classes.example_classes.PositionTypeWrapper, t_PositionTypeWrapper, properties = dict(position_type=t_PositionTypeWrapper.c.position_type))

m_Position4D = mapper_registry.map_imperatively(classes.example_classes.Position4D, t_Position4D, )

m_OGSimObjSubclass = mapper_registry.map_imperatively(classes.example_classes.OGSimObjSubclass, t_OGSimObjSubclass, properties = dict(pose=relationship('Pose',foreign_keys=[t_OGSimObjSubclass.c.pose_id]), 
concept=t_OGSimObjSubclass.c.concept))

m_Molecule = mapper_registry.map_imperatively(classes.example_classes.Molecule, t_Molecule, properties = dict(atoms=relationship('Atom',foreign_keys=[t_Atom.c.molecule_atoms_id]), 
bonds=relationship('Bond',foreign_keys=[t_Bond.c.molecule_bonds_id])))

m_Bond = mapper_registry.map_imperatively(classes.example_classes.Bond, t_Bond, properties = dict(atom1=relationship('Atom',foreign_keys=[t_Bond.c.atom1_id]), 
atom2=relationship('Atom',foreign_keys=[t_Bond.c.atom2_id])))

m_Position5D = mapper_registry.map_imperatively(classes.example_classes.Position5D, t_Position5D, polymorphic_identity = "Position5D", inherits = m_Position)

m_MultipleInheritance = mapper_registry.map_imperatively(classes.example_classes.MultipleInheritance, t_MultipleInheritance, polymorphic_identity = "MultipleInheritance", inherits = m_Parent1)
