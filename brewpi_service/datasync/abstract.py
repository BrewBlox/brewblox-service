from abc import abstractmethod

from circuits import Component

class AbstractControllerSyncherBackend:
    """
    A Syncher Backend implements a way to sync a Hardware Device (Controller)
    with the service.
    """
    pass

class AbstractForwarder:
    """
    Forwards synched data to some other systems so they can sync at their turn.
    """
    @abstractmethod
    def on_controller_appeared(self, event):
        raise NotImplementedError

    @abstractmethod
    def on_controller_disappeared(self, event):
        raise NotImplementedError


class AbstractBackstoreSyncher:
    """
    Implements a syncher that takes care of receiving events from `Backends`
    and persist data into a backing store.
    """
    @abstractmethod
    def on_controller_appeared(self, event):
        raise NotImplementedError

    @abstractmethod
    def on_controller_disappeared(self, event):
        raise NotImplementedError


class AbstractDeviceSyncher:
    @abstractmethod
    def update(self, controller, state, event):
        raise NotImplementedError
