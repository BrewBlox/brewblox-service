import coloredlogs

from brewpi_service.datasync import DataSyncherServer

coloredlogs.install(level='DEBUG')

syncher = DataSyncherServer()

syncher.run()


