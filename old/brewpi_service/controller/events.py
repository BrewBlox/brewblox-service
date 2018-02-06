from circuits import Event


class ControllerConnected(Event):
    """
    When a controller connects
    """
    def __init__(self, aController):
        super(ControllerConnected, self).__init__()
        self.controller = aController


class ControllerDisconnected(Event):
    def __init__(self, aController):
        super(ControllerDisconnected, self).__init__()
        self.controller = aController


class ControllerBlockList(Event):
    def __init__(self, aController, aBlockList):
        super(ControllerBlockList, self).__init__()
        self.controller = aController
        self.blocks = aBlockList


class ControllerStateChangeRequest(Event):
    def __init__(self, aController, changes):
        super(ControllerStateChangeRequest, self).__init__()
        self.controller = aController
        self.changes = changes


class ControllerRequestCurrentProfile(Event):
    pass


class ControllerCleanStaleAvailableBlocks(Event):
    """
    Ask persisting backstores to remove all stale blocks
    """
    def __init__(self, aController, time_limit):
        super(ControllerCleanStaleAvailableBlocks, self).__init__()
        self.controller = aController
        self.time_limit = time_limit


