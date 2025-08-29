import unittest

from sqlalchemy import create_engine, Engine, select
from sqlalchemy.orm import Session, configure_mappers

from classes.example_classes import *
from classes.sqlalchemy_interface import *
from ormatic.dao import to_dao, NoDAOFoundDuringParsingError, is_data_column
from ormatic.utils import drop_database


class InterfaceTestCase(unittest.TestCase):
    session: Session
    engine: Engine

    @classmethod
    def setUpClass(cls):
        # Logger configuration is now handled in ormatic/__init__.py
        configure_mappers()

        cls.engine = create_engine('sqlite:///:memory:')
        cls.session = Session(cls.engine)

    def setUp(self):
        Base.metadata.create_all(self.engine)

    def tearDown(self):
        drop_database(self.engine)
        #Base.metadata.drop_all(self.engine)

    @classmethod
    def tearDownClass(cls):
        cls.session.close()
        cls.engine.dispose()

    def test_position(self):
        p1 = Position(1, 2, 3)

        p1dao: PositionDAO = PositionDAO.to_dao(p1)
        self.assertEqual(p1.x, p1dao.x)
        self.assertEqual(p1.y, p1dao.y)
        self.assertEqual(p1.z, p1dao.z)

        self.session.add(p1dao)
        self.session.commit()

        # test the content of the database
        queried_p1 = self.session.scalars(select(PositionDAO)).one()

        self.assertEqual(p1.x, queried_p1.x)
        self.assertEqual(p1.y, queried_p1.y)
        self.assertEqual(p1.z, queried_p1.z)

        p1_reconstructed = queried_p1.from_dao()
        self.assertEqual(p1, p1_reconstructed)

    def test_position4d(self):
        p4d = Position4D(1.0, 2.0, 3.0, 4.0)

        p4d_dao = Position4DDAO.to_dao(p4d)
        self.assertEqual(p4d.x, p4d_dao.x)
        self.assertEqual(p4d.y, p4d_dao.y)
        self.assertEqual(p4d.z, p4d_dao.z)
        self.assertEqual(p4d.w, p4d_dao.w)

        self.session.add(p4d_dao)
        self.session.commit()

        # test the content of the database
        # Note: Polymorphic queries don't work correctly yet, so we query directly for Position4DDAO objects
        queried_p4d = self.session.scalars(select(PositionDAO)).one()

        self.assertEqual(p4d.x, queried_p4d.x)
        self.assertEqual(p4d.y, queried_p4d.y)
        self.assertEqual(p4d.z, queried_p4d.z)
        self.assertEqual(p4d.w, queried_p4d.w)

        p4d_reconstructed = queried_p4d.from_dao()
        self.assertEqual(p4d, p4d_reconstructed)

    def test_orientation(self):
        o1 = Orientation(1.0, 2.0, 3.0, None)

        o1dao = OrientationDAO.to_dao(o1)
        self.assertEqual(o1.x, o1dao.x)
        self.assertEqual(o1.y, o1dao.y)
        self.assertEqual(o1.z, o1dao.z)
        self.assertEqual(o1.w, o1dao.w)

        self.session.add(o1dao)
        self.session.commit()

        # test the content of the database
        queried_o1 = self.session.scalars(select(OrientationDAO)).one()

        self.assertEqual(o1.x, queried_o1.x)
        self.assertEqual(o1.y, queried_o1.y)
        self.assertEqual(o1.z, queried_o1.z)
        self.assertEqual(o1.w, queried_o1.w)

        o1_reconstructed = queried_o1.from_dao()
        self.assertEqual(o1, o1_reconstructed)

    def test_pose(self):
        p1 = Position(1, 2, 3)
        o1 = Orientation(1.0, 2.0, 3.0, None)
        pose = Pose(p1, o1)

        posedao = PoseDAO.to_dao(pose)
        self.assertIsInstance(posedao.position, PositionDAO)
        self.assertIsInstance(posedao.orientation, OrientationDAO)

        self.session.add(posedao)
        self.session.commit()

        queried = self.session.scalars(select(PoseDAO)).one()
        self.assertIsNotNone(queried.position)
        self.assertIsNotNone(queried.orientation)
        self.assertEqual(queried, posedao)
        queried = queried.from_dao()
        self.assertEqual(pose, queried)

    def test_atom(self):
        atom = Atom(Element.C, 1, 2.)
        atomdao = AtomDAO.to_dao(atom)
        self.assertEqual(atomdao.element, Element.C)

        self.session.add(atomdao)
        self.session.commit()

        queried = self.session.scalars(select(AtomDAO)).one()
        self.assertIsInstance(queried.element, Element)

        atom_from_session = queried.from_dao()
        self.assertEqual(atom, atom_from_session)

    def test_entity_and_derived(self):
        entity = Entity("TestEntity")
        derived = DerivedEntity("DerivedEntity")

        entity_dao = to_dao(entity)
        derived_dao = to_dao(derived)

        self.session.add(entity_dao)
        self.session.add(derived_dao)
        self.session.commit()

        # test the content of the database
        queried_entity = self.session.scalars(select(CustomEntityDAO)).first()
        queried_derived = self.session.scalars(select(DerivedEntityDAO)).first()

        self.assertEqual(entity.name, queried_entity.overwritten_name)
        self.assertEqual(derived.name, queried_derived.overwritten_name)
        self.assertEqual(derived.description, queried_derived.description)

        entity_reconstructed = queried_entity.from_dao()
        derived_reconstructed = queried_derived.from_dao()

        self.assertEqual(entity.name, entity_reconstructed.name)
        self.assertEqual(derived.name, derived_reconstructed.name)
        self.assertEqual(derived.description, derived_reconstructed.description)

    def test_parent_and_child(self):
        parent = Parent("TestParent")
        child_mapped = ChildMapped("ChildMapped", 42)
        child_not_mapped = ChildNotMapped("a", 2, {})

        parent_dao = to_dao(parent)
        child_dao = to_dao(child_mapped)

        self.assertEqual(parent.name, parent_dao.name)
        self.assertEqual(child_mapped.name, child_dao.name)
        self.assertEqual(child_mapped.attribute1, child_dao.attribute1)

        self.session.add(parent_dao)
        self.session.add(child_dao)
        self.session.commit()

        # test the content of the database
        queried_parent = self.session.scalars(select(ParentDAO)).all()
        queried_child = self.session.scalars(select(ChildMappedDAO)).all()

        self.assertTrue(child_dao in queried_parent)
        self.assertTrue(queried_child[0] in queried_parent)

        self.assertEqual(parent.name, queried_parent[0].name)
        self.assertEqual(child_mapped.name, queried_child[0].name)
        self.assertEqual(child_mapped.attribute1, queried_child[0].attribute1)

        parent_reconstructed = queried_parent[0].from_dao()
        child_reconstructed = queried_child[0].from_dao()

        self.assertEqual(parent.name, parent_reconstructed.name)
        self.assertEqual(child_mapped.name, child_reconstructed.name)
        self.assertEqual(child_mapped.attribute1, child_reconstructed.attribute1)

    def test_node(self):
        n1 = Node()
        n2 = Node(parent=n1)
        n3 = Node(parent=n1)

        n2dao = NodeDAO.to_dao(n2)

        self.session.add(n2dao)
        self.session.commit()

        results = self.session.scalars(select(NodeDAO)).all()
        self.assertEqual(len(results), 2)

    def test_position_type_wrapper(self):
        wrapper = PositionTypeWrapper(Position)
        dao = PositionTypeWrapperDAO.to_dao(wrapper)
        self.assertEqual(dao.position_type, wrapper.position_type)
        self.session.add(dao)
        self.session.commit()

        result = self.session.scalars(select(PositionTypeWrapperDAO)).one()
        self.assertEqual(result, dao)

    def test_positions(self):
        p1 = Position(1, 2, 3)
        p2 = Position(2, 3, 4)
        positions = Positions([p1, p2], ["a", "b", "c"])
        dao = PositionsDAO.to_dao(positions)
        self.assertEqual(len(dao.positions), 2)

        self.session.add(dao)
        self.session.commit()

        positions_results = self.session.scalars(select(PositionDAO)).all()
        self.assertEqual(len(positions_results), 2)

        result = self.session.scalars(select(PositionsDAO)).one()
        self.assertEqual(result.some_strings, positions.some_strings)

        self.assertEqual(len(result.positions), 2)

    def test_double_position_aggregator(self):
        p1, p2, p3 = Position(1, 2, 3), Position(2, 3, 4), Position(3, 4, 5)
        dpa = DoublePositionAggregator([p1, p2], [p1, p3])
        dpa_dao = DoublePositionAggregatorDAO.to_dao(dpa)
        self.session.add(dpa_dao)
        self.session.commit()

        queried_positions = self.session.scalars(select(PositionDAO)).all()
        self.assertEqual(len(queried_positions), 3)

        queried = self.session.scalars(select(DoublePositionAggregatorDAO)).one()
        self.assertEqual(queried, dpa_dao)
        self.assertTrue(queried.positions1[0] in queried_positions)

    def test_kinematic_chain_and_torso(self):
        k1 = KinematicChain("a")
        k2 = KinematicChain("b")
        torso = Torso("t", [k1, k2])
        torso_dao = TorsoDAO.to_dao(torso)

        self.session.add(torso_dao)
        self.session.commit()

        queried_torso = self.session.scalars(select(TorsoDAO)).one()
        self.assertEqual(queried_torso, torso_dao)

    def test_custom_types(self):
        ogs = OriginalSimulatedObject(Bowl(), 1)
        ogs_dao = OriginalSimulatedObjectDAO.to_dao(ogs)
        self.assertEqual(ogs.concept, ogs_dao.concept)

        self.session.add(ogs_dao)
        self.session.commit()

        queried = self.session.scalars(select(OriginalSimulatedObjectDAO)).one()
        self.assertEqual(ogs_dao, queried)
        self.assertIsInstance(queried.concept, Bowl)

    def test_inheriting_from_explicit_mapping(self):
        entity: DerivedEntity = DerivedEntity(name="TestEntity")

        entity_dao = DerivedEntityDAO.to_dao(entity)
        self.assertIsInstance(entity_dao, DerivedEntityDAO)
        self.session.add(entity_dao)
        self.session.commit()

        queried_entities_og = self.session.scalars(select(CustomEntityDAO)).all()
        queried_entity = self.session.scalars(select(DerivedEntityDAO)).one()
        self.assertTrue(queried_entity.description is not None)
        self.assertTrue(queried_entity.overwritten_name is not None)
        self.assertTrue(queried_entity in queried_entities_og)

        reconstructed = queried_entity.from_dao()
        self.assertEqual(reconstructed, entity)

    def test_entity_association(self):
        entity = Entity("TestEntity")
        association = EntityAssociation(entity=entity, a=["a"])

        association_dao = to_dao(association)

        self.assertIsInstance(association_dao, EntityAssociationDAO)
        self.assertIsInstance(association_dao.entity, CustomEntityDAO)

        self.session.add(association_dao)
        self.session.commit()

        queried_association = self.session.scalars(select(EntityAssociationDAO)).one()
        self.assertEqual(queried_association.entity.overwritten_name, entity.name)
        reconstructed = queried_association.from_dao()
        self.assertEqual(reconstructed, association)

    def test_assertion(self):
        p = Pose([1,2,3], "a")
        self.assertRaises(NoDAOFoundDuringParsingError, to_dao, p)

    def test_PositionsSubclassWithAnotherPosition(self):
        position = Position(1, 2, 3)
        obj = PositionsSubclassWithAnotherPosition([position], ["a","b", "c"], position)
        dao: PositionsSubclassWithAnotherPositionDAO = to_dao(obj)

        self.session.add(dao)
        self.session.commit()

    def test_inheriting_from_inherited_class(self):
        position_5d = Position5D(1, 2, 3, 4, 5)
        position_4d = Position4D(1, 2, 3, 4)

        position_4d_dao = to_dao(position_4d)
        position_5d_dao = to_dao(position_5d)

        self.session.add(position_4d_dao)
        self.session.commit()

        self.session.add(position_5d_dao)
        self.session.commit()

        queried_position_5d = self.session.scalars(select(Position5DDAO)).one()
        queried_position_4d = self.session.scalars(select(Position4DDAO)).all()
        queried_position = self.session.scalars(select(PositionDAO)).all()
        columns = [column for column in queried_position_5d.__table__.columns if is_data_column(column)]
        self.assertTrue(queried_position_5d in queried_position_4d)
        self.assertTrue(queried_position_5d in queried_position)
        self.assertTrue(queried_position_4d[0] in queried_position)
        self.assertEqual(len(columns), 1) #w column

    def test_backreference_with_mapping(self):
        back_ref = Backreference({1:1})
        ref = Reference(0, back_ref)
        back_ref.reference = ref

        dao = to_dao(ref)
        self.session.add(dao)
        self.session.commit()
        reconstructed = dao.from_dao()

        # Check individual properties instead of comparing entire objects
        self.assertEqual(reconstructed.value, ref.value)
        self.assertIsNotNone(reconstructed.backreference)
        self.assertEqual(reconstructed.backreference.unmappable, back_ref.unmappable)

        # Check that the circular reference is correctly reconstructed
        self.assertIs(reconstructed.backreference.reference, reconstructed)

    def test_alternative_mapping_aggregator(self):
        e1 = Entity("E1")
        e2 = Entity("E2")
        e3 = Entity("E3")

        ama = AlternativeMappingAggregator([e1, e2], [e2, e3])
        dao = to_dao(ama)

        self.assertIs(dao.entities1[1], dao.entities2[0])

        self.session.add(dao)
        self.session.commit()

        queried = self.session.scalars(select(AlternativeMappingAggregatorDAO)).one()
        reconstructed = queried.from_dao()
        self.assertIs(reconstructed.entities1[1], reconstructed.entities2[0])


    def test_container_item(self):
        i1 = ItemWithBackreference(0)
        i2 = ItemWithBackreference(1)
        container = Container([i1, i2])

        dao = to_dao(container)
        self.session.add(dao)
        self.session.commit()

        queried_items = self.session.scalars(select(ItemWithBackreferenceDAO)).all()
        self.assertEqual(len(queried_items), 2)

        queried_container = self.session.scalar(select(ContainerDAO))
        self.assertIs(queried_container, queried_items[0].container)

        reconstructed_item = queried_items[0].from_dao()
        self.assertEqual(len(reconstructed_item.container.items), 2)


    def test_nested_mappings(self):
        shape_1 = Shape("rectangle", Transformation(Vector(1), Rotation(1)))
        shape_2 = Shape("circle", Transformation(Vector(2), Rotation(2)))
        shape_3 = Shape("rectangle", Transformation(Vector(3), Rotation(3)))
        shapes = Shapes([shape_1, shape_2, shape_3])
        more_shapes = MoreShapes([shapes, shapes])
        dao = to_dao(more_shapes)
        self.session.add(dao)
        self.session.commit()

    def test_vector_mapped(self):
        vector = Vector(1.0)
        vector_mapped = VectorsWithProperty([vector])
        dao = to_dao(vector_mapped)

        self.session.add(dao)
        self.session.commit()

        queried = self.session.scalars(select(VectorsWithPropertyMappedDAO)).one()
        reconstructed = queried.from_dao()

        self.assertEqual(reconstructed.vectors[0].x, vector.x)

    def test_test_classes(self):
        parent = ParentBase("x", 0)
        child = ChildBase("y", 0)
        parent_mapping = ParentBaseMapping("x")
        child_mapping = ChildBaseMapping("y")

        parent_dao = to_dao(parent_mapping)
        child_dao = to_dao(child_mapping)

        self.session.add_all([parent_dao, child_dao])
        self.session.commit()

        child_result_dao = self.session.scalars(select(ChildBaseMappingDAO)).one()
        parent_result_dao = self.session.scalars(select(ParentBaseMappingDAO)).first()

        child_from_dao = child_result_dao.from_dao()
        parent_from_dao = parent_result_dao.from_dao()

        self.assertEqual(child_result_dao, child_dao)
        self.assertEqual(parent_result_dao, parent_dao)
        self.assertEqual(child_from_dao, child)
        self.assertEqual(parent_from_dao, parent)

    def test_private_factories(self):
        obj = PrivateDefaultFactory()
        dao = to_dao(obj)
        reconstructed: PrivateDefaultFactory = dao.from_dao()
        self.assertEqual(reconstructed._private_list, [])


if __name__ == '__main__':
    unittest.main()
