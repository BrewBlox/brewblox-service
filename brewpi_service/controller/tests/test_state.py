from unittest import TestCase
from unittest.mock import Mock

from ..state import (
    ControllerState,
    ControllerStateManager,
    ControllerStateTransaction
)


class TestControllerState(TestCase):
    def test_simple_creation(self):
        manager = ControllerStateManager()
        state = ControllerState(manager)

    def test_begin_transaction(self):
        manager = ControllerStateManager()
        state = ControllerState(manager)

        transaction = state.begin_transaction()

        self.assertTrue(isinstance(transaction, ControllerStateTransaction))
        self.assertEqual(transaction.get_compiled_changes(), [])


class TestControllerStateTransaction(TestCase):
    def setUp(self):
        self.transaction = ControllerStateTransaction()

    def test_no_block_no_change(self):
        changes = self.transaction.get_compiled_changes()
        self.assertEqual(changes, [])

    def test_one_block_no_change(self):
        block = Mock()
        block.get_dirty_fields = Mock(return_value=[])
        self.transaction.add(block)

        changes = self.transaction.get_compiled_changes()

        block.get_dirty_fields.assert_called_once()
        self.assertEqual(changes, [])

    def test_one_block_one_change(self):
        block = Mock()
        block.changed_field = Mock()
        block.changed_field.get_requested_value = Mock(return_value='new_value')
        block.get_dirty_fields = Mock(return_value=['changed_field'])

        self.transaction.add(block)

        changes = self.transaction.get_compiled_changes()

        self.assertEqual(len(changes), 1)
        self.assertEqual(len(changes[0]), 3)
        self.assertEqual(changes[0][0], block)
        self.assertEqual(changes[0][1], 'changed_field')
        self.assertEqual(changes[0][2], 'new_value')

        block.get_dirty_fields.assert_called_once()
        block.changed_field.get_requested_value.assert_called_once()

    def test_clear(self):
        block = Mock()
        block.get_dirty_fields = Mock(return_value=[])

        self.transaction.add(block)
        changes = self.transaction.get_compiled_changes()

        block.get_dirty_fields.assert_called_once()
        self.assertEqual(changes, [])

        # Now, clear
        self.transaction.clear()
        changes = self.transaction.get_compiled_changes()
        self.assertEqual(changes, [])

