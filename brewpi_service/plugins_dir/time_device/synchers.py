from brewpi_service.datasync.abstract import AbstractDeviceSyncher

class ScaledTimeSyncher(AbstractDeviceSyncher):
    def update(self, controller, state, event):
        object_id = int.from_bytes(event.idchain, byteorder="little", signed=False)
        print("controller: {0}".format(event.connector))
        print("updateeeeee!: {0}".format(state))
