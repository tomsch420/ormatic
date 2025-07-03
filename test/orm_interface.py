from classes.example_classes import Atom, Bond, ChildMapped, DerivedEntity, DoublePositionAggregator, EntityDAO, EnumContainer, KinematicChain, Molecule, MultipleInheritance, Node, OGSimObjSubclass, ObjectAnnotation, Orientation, Parent, Parent1, Parent2, PartialPosition, PhysicalObjectType, Pose, Position, Position5D, PositionTypeWrapper, Positions, SimulatedObject, Torso
from ormatic.custom_types import TypeType
from ormatic.dao import DataAccessObject
from typing import Any, List, Optional

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column, relationship
import classes.example_classes

class Base(MappedAsDataclass, DeclarativeBase):
    pass


class DerivedEntityDAO(Base, DataAccessObject[DerivedEntity]):
    __tablename__ = 'DerivedEntityDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(255))


class DoublePositionAggregatorDAO(Base, DataAccessObject[DoublePositionAggregator]):
    __tablename__ = 'DoublePositionAggregatorDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    PositionDAO: Mapped[List['PositionDAO']] = relationship('PositionDAO', foreign_keys='[PositionDAO.doublepositionaggregator_positions1_id]', back_populates='doublepositionaggregator_positions1')
    PositionDAO_: Mapped[List['PositionDAO']] = relationship('PositionDAO', foreign_keys='[PositionDAO.doublepositionaggregator_positions2_id]', back_populates='doublepositionaggregator_positions2')


class EntityDAODAO(Base, DataAccessObject[EntityDAO]):
    __tablename__ = 'EntityDAODAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))


class EnumContainerDAO(Base, DataAccessObject[EnumContainer]):
    __tablename__ = 'EnumContainerDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[classes.example_classes.ValueEnum] = mapped_column(Enum('A', 'B', 'C', name='valueenum'))


class KinematicChainDAO(Base, DataAccessObject[KinematicChain]):
    __tablename__ = 'KinematicChainDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    polymorphic_type: Mapped[Optional[str]] = mapped_column(String(255))


class MoleculeDAO(Base, DataAccessObject[Molecule]):
    __tablename__ = 'MoleculeDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ind1: Mapped[int] = mapped_column(Integer)
    inda: Mapped[int] = mapped_column(Integer)
    logp: Mapped[float] = mapped_column(Float)
    lumo: Mapped[float] = mapped_column(Float)
    mutagenic: Mapped[bool] = mapped_column(Boolean)

    AtomDAO: Mapped[List['AtomDAO']] = relationship('AtomDAO', back_populates='molecule_atoms')
    BondDAO: Mapped[List['BondDAO']] = relationship('BondDAO', back_populates='molecule_bonds')


class NodeDAO(Base, DataAccessObject[Node]):
    __tablename__ = 'NodeDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey('NodeDAO.id'))

    parent: Mapped[Optional['NodeDAO']] = relationship('NodeDAO', remote_side=[id], back_populates='parent_reverse')
    parent_reverse: Mapped[List['NodeDAO']] = relationship('NodeDAO', remote_side=[parent_id], back_populates='parent')


class ObjectAnnotationDAO(Base, DataAccessObject[ObjectAnnotation]):
    __tablename__ = 'ObjectAnnotationDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class OrientationDAO(Base, DataAccessObject[Orientation]):
    __tablename__ = 'OrientationDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    z: Mapped[float] = mapped_column(Float)
    w: Mapped[Optional[float]] = mapped_column(Float)

    PoseDAO: Mapped[List['PoseDAO']] = relationship('PoseDAO', back_populates='orientation')


class Parent1DAO(Base, DataAccessObject[Parent1]):
    __tablename__ = 'Parent1DAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    obj: Mapped[str] = mapped_column(String(255))
    polymorphic_type: Mapped[Optional[str]] = mapped_column(String(255))


class Parent2DAO(Base, DataAccessObject[Parent2]):
    __tablename__ = 'Parent2DAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    obj2: Mapped[str] = mapped_column(String(255))


class ParentDAO(Base, DataAccessObject[Parent]):
    __tablename__ = 'ParentDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    polymorphic_type: Mapped[Optional[str]] = mapped_column(String(255))


class PartialPositionDAO(Base, DataAccessObject[PartialPosition]):
    __tablename__ = 'PartialPositionDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    z: Mapped[float] = mapped_column(Float)


class PositionTypeWrapperDAO(Base, DataAccessObject[PositionTypeWrapper]):
    __tablename__ = 'PositionTypeWrapperDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_type: Mapped[Optional[Any]] = mapped_column(TypeType)


class PositionsDAO(Base, DataAccessObject[Positions]):
    __tablename__ = 'PositionsDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    some_strings: Mapped[Optional[dict]] = mapped_column(JSON)

    PositionDAO: Mapped[List['PositionDAO']] = relationship('PositionDAO', back_populates='positions_positions')


class AtomDAO(Base, DataAccessObject[Atom]):
    __tablename__ = 'AtomDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    element: Mapped[classes.example_classes.Element] = mapped_column(Enum('C', 'H', 'O', 'N', 'F', 'B', 'I', name='element'))
    type: Mapped[int] = mapped_column(Integer)
    charge: Mapped[float] = mapped_column(Float)
    molecule_atoms_id: Mapped[Optional[int]] = mapped_column(ForeignKey('MoleculeDAO.id'))

    molecule_atoms: Mapped[Optional['MoleculeDAO']] = relationship('MoleculeDAO', back_populates='AtomDAO')
    BondDAO: Mapped[List['BondDAO']] = relationship('BondDAO', foreign_keys='[BondDAO.atom1_id]', back_populates='atom1')
    BondDAO_: Mapped[List['BondDAO']] = relationship('BondDAO', foreign_keys='[BondDAO.atom2_id]', back_populates='atom2')


class ChildMappedDAO(ParentDAO, DataAccessObject[ChildMapped]):
    __tablename__ = 'ChildMappedDAO'

    id: Mapped[int] = mapped_column(ForeignKey('ParentDAO.id'), primary_key=True)
    attribute1: Mapped[int] = mapped_column(Integer)


class MultipleInheritanceDAO(Parent1DAO, DataAccessObject[MultipleInheritance]):
    __tablename__ = 'MultipleInheritanceDAO'

    id: Mapped[int] = mapped_column(ForeignKey('Parent1DAO.id'), primary_key=True)
    obj2: Mapped[str] = mapped_column(String(255))


class PositionDAO(Base, DataAccessObject[Position]):
    __tablename__ = 'PositionDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    z: Mapped[float] = mapped_column(Float)
    doublepositionaggregator_positions1_id: Mapped[Optional[int]] = mapped_column(ForeignKey('DoublePositionAggregatorDAO.id'))
    doublepositionaggregator_positions2_id: Mapped[Optional[int]] = mapped_column(ForeignKey('DoublePositionAggregatorDAO.id'))
    positions_positions_id: Mapped[Optional[int]] = mapped_column(ForeignKey('PositionsDAO.id'))
    polymorphic_type: Mapped[Optional[str]] = mapped_column(String(255))

    doublepositionaggregator_positions1: Mapped[Optional['DoublePositionAggregatorDAO']] = relationship('DoublePositionAggregatorDAO', foreign_keys=[doublepositionaggregator_positions1_id], back_populates='PositionDAO')
    doublepositionaggregator_positions2: Mapped[Optional['DoublePositionAggregatorDAO']] = relationship('DoublePositionAggregatorDAO', foreign_keys=[doublepositionaggregator_positions2_id], back_populates='PositionDAO_')
    positions_positions: Mapped[Optional['PositionsDAO']] = relationship('PositionsDAO', back_populates='PositionDAO')
    PoseDAO: Mapped[List['PoseDAO']] = relationship('PoseDAO', back_populates='position')


class TorsoDAO(KinematicChainDAO, DataAccessObject[Torso]):
    __tablename__ = 'TorsoDAO'

    id: Mapped[int] = mapped_column(ForeignKey('KinematicChainDAO.id'), primary_key=True)


class BondDAO(Base, DataAccessObject[Bond]):
    __tablename__ = 'BondDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    atom1_id: Mapped[int] = mapped_column(ForeignKey('AtomDAO.id'))
    atom2_id: Mapped[int] = mapped_column(ForeignKey('AtomDAO.id'))
    type: Mapped[int] = mapped_column(Integer)
    molecule_bonds_id: Mapped[Optional[int]] = mapped_column(ForeignKey('MoleculeDAO.id'))

    atom1: Mapped['AtomDAO'] = relationship('AtomDAO', foreign_keys=[atom1_id], back_populates='BondDAO')
    atom2: Mapped['AtomDAO'] = relationship('AtomDAO', foreign_keys=[atom2_id], back_populates='BondDAO_')
    molecule_bonds: Mapped[Optional['MoleculeDAO']] = relationship('MoleculeDAO', back_populates='BondDAO')


class PoseDAO(Base, DataAccessObject[Pose]):
    __tablename__ = 'PoseDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey('PositionDAO.id'))
    orientation_id: Mapped[int] = mapped_column(ForeignKey('OrientationDAO.id'))

    orientation: Mapped['OrientationDAO'] = relationship('OrientationDAO', back_populates='PoseDAO')
    position: Mapped['PositionDAO'] = relationship('PositionDAO', back_populates='PoseDAO')
    OGSimObjSubclassDAO: Mapped[List['OGSimObjSubclassDAO']] = relationship('OGSimObjSubclassDAO', back_populates='pose')
    SimulatedObjectDAO: Mapped[List['SimulatedObjectDAO']] = relationship('SimulatedObjectDAO', back_populates='pose')


class Position5DDAO(PositionDAO, DataAccessObject[Position5D]):
    __tablename__ = 'Position5DDAO'

    id: Mapped[int] = mapped_column(ForeignKey('PositionDAO.id'), primary_key=True)
    a: Mapped[float] = mapped_column(Float)


class OGSimObjSubclassDAO(Base, DataAccessObject[OGSimObjSubclass]):
    __tablename__ = 'OGSimObjSubclassDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept: Mapped[Any] = mapped_column(PhysicalObjectType)
    pose_id: Mapped[int] = mapped_column(ForeignKey('PoseDAO.id'))
    placeholder: Mapped[float] = mapped_column(Float)

    pose: Mapped['PoseDAO'] = relationship('PoseDAO', back_populates='OGSimObjSubclassDAO')


class SimulatedObjectDAO(Base, DataAccessObject[SimulatedObject]):
    __tablename__ = 'SimulatedObjectDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    concept: Mapped[Any] = mapped_column(PhysicalObjectType)
    pose_id: Mapped[int] = mapped_column(ForeignKey('PoseDAO.id'))

    pose: Mapped['PoseDAO'] = relationship('PoseDAO', back_populates='SimulatedObjectDAO')
