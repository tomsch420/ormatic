from classes.example_classes import Atom, ChildMapped, DerivedEntity, DoublePositionAggregator, Entity, KinematicChain, Node, ObjectAnnotation, Orientation, OriginalSimulatedObject, Parent, Pose, Position, Position4D, PositionTypeWrapper, Positions, Torso
from ormatic.custom_types import TypeType
from ormatic.dao import DataAccessObject
from typing import Any, List, Optional

from sqlalchemy import Enum, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import classes.example_classes

class Base(DeclarativeBase):
    pass


class AtomDAO(Base, DataAccessObject[Atom]):
    __tablename__ = 'AtomDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    element: Mapped[classes.example_classes.Element] = mapped_column(Enum('C', 'H', name='element'))
    type: Mapped[int] = mapped_column(Integer)
    charge: Mapped[float] = mapped_column(Float)


class DoublePositionAggregatorDAO(Base, DataAccessObject[DoublePositionAggregator]):
    __tablename__ = 'DoublePositionAggregatorDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    PositionDAO: Mapped[List['PositionDAO']] = relationship('PositionDAO', foreign_keys='[PositionDAO.doublepositionaggregator_positions1_id]', back_populates='doublepositionaggregator_positions1')
    PositionDAO_: Mapped[List['PositionDAO']] = relationship('PositionDAO', foreign_keys='[PositionDAO.doublepositionaggregator_positions2_id]', back_populates='doublepositionaggregator_positions2')


class EntityDAO(Base, DataAccessObject[Entity]):
    __tablename__ = 'EntityDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    polymorphic_type: Mapped[Optional[str]] = mapped_column(String(255))


class KinematicChainDAO(Base, DataAccessObject[KinematicChain]):
    __tablename__ = 'KinematicChainDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    polymorphic_type: Mapped[Optional[str]] = mapped_column(String(255))


class NodeDAO(Base, DataAccessObject[Node]):
    __tablename__ = 'NodeDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey('NodeDAO.id'))

    parent: Mapped[Optional['NodeDAO']] = relationship('NodeDAO', remote_side=[id], back_populates='parent_reverse')
    parent_reverse: Mapped[List['NodeDAO']] = relationship('NodeDAO', remote_side=[parent_id], back_populates='parent')


class OrientationDAO(Base, DataAccessObject[Orientation]):
    __tablename__ = 'OrientationDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    z: Mapped[float] = mapped_column(Float)
    w: Mapped[Optional[float]] = mapped_column(Float)

    PoseDAO: Mapped[List['PoseDAO']] = relationship('PoseDAO', back_populates='orientation')


class ParentDAO(Base, DataAccessObject[Parent]):
    __tablename__ = 'ParentDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    polymorphic_type: Mapped[Optional[str]] = mapped_column(String(255))


class PositionTypeWrapperDAO(Base, DataAccessObject[PositionTypeWrapper]):
    __tablename__ = 'PositionTypeWrapperDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_type: Mapped[Optional[Any]] = mapped_column(TypeType)


class PositionsDAO(Base, DataAccessObject[Positions]):
    __tablename__ = 'PositionsDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    some_strings: Mapped[Optional[dict]] = mapped_column(JSON)

    PositionDAO: Mapped[List['PositionDAO']] = relationship('PositionDAO', back_populates='positions_positions')


class ChildMappedDAO(ParentDAO, DataAccessObject[ChildMapped]):
    __tablename__ = 'ChildMappedDAO'

    id: Mapped[int] = mapped_column(ForeignKey('ParentDAO.id'), primary_key=True)
    attribute1: Mapped[int] = mapped_column(Integer)


class DerivedEntityDAO(EntityDAO, DataAccessObject[DerivedEntity]):
    __tablename__ = 'DerivedEntityDAO'

    id: Mapped[int] = mapped_column(ForeignKey('EntityDAO.id'), primary_key=True)
    description: Mapped[str] = mapped_column(String(255))


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


class PoseDAO(Base, DataAccessObject[Pose]):
    __tablename__ = 'PoseDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey('PositionDAO.id'))
    orientation_id: Mapped[int] = mapped_column(ForeignKey('OrientationDAO.id'))

    orientation: Mapped['OrientationDAO'] = relationship('OrientationDAO', back_populates='PoseDAO')
    position: Mapped['PositionDAO'] = relationship('PositionDAO', back_populates='PoseDAO')
    OriginalSimulatedObjectDAO: Mapped[List['OriginalSimulatedObjectDAO']] = relationship('OriginalSimulatedObjectDAO', back_populates='pose')


class Position4DDAO(PositionDAO, DataAccessObject[Position4D]):
    __tablename__ = 'Position4DDAO'

    id: Mapped[int] = mapped_column(ForeignKey('PositionDAO.id'), primary_key=True)
    w: Mapped[float] = mapped_column(Float)


class OriginalSimulatedObjectDAO(Base, DataAccessObject[OriginalSimulatedObject]):
    __tablename__ = 'OriginalSimulatedObjectDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pose_id: Mapped[int] = mapped_column(ForeignKey('PoseDAO.id'))
    placeholder: Mapped[float] = mapped_column(Float)

    pose: Mapped['PoseDAO'] = relationship('PoseDAO', back_populates='OriginalSimulatedObjectDAO')
    ObjectAnnotationDAO: Mapped[List['ObjectAnnotationDAO']] = relationship('ObjectAnnotationDAO', back_populates='object_reference')


class ObjectAnnotationDAO(Base, DataAccessObject[ObjectAnnotation]):
    __tablename__ = 'ObjectAnnotationDAO'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    object_reference_id: Mapped[int] = mapped_column(ForeignKey('OriginalSimulatedObjectDAO.id'))

    object_reference: Mapped['OriginalSimulatedObjectDAO'] = relationship('OriginalSimulatedObjectDAO', back_populates='ObjectAnnotationDAO')
