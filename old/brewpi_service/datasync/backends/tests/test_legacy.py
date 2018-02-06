from unittest.mock import Mock

from brewpi_service.datasync.backends.brewpi_legacy import AvailableDevicePool

class TestAvailableDevicePool:
    def test_simple_insert(self):
        pool = AvailableDevicePool()

        device1 = Mock()

        id = pool.get_id_for(device1)

        assert(type(id) is int)

    def test_same_insert(self):
        pool = AvailableDevicePool()

        device1 = Mock()

        id1 = pool.get_id_for(device1)
        id2 = pool.get_id_for(device1)

        assert(id1 == id2)

    def test_two_inserts(self):
        pool = AvailableDevicePool()

        device1 = Mock()
        device2 = Mock()

        id1 = pool.get_id_for(device1)
        id2 = pool.get_id_for(device2)

        assert(id1 != id2)

