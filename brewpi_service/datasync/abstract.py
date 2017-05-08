from abc import abstractmethod, ABC


class AbstractControllerSyncherBackend(ABC):
    """
    A Syncher Backend implements a way to sync a Hardware Device (Controller)
    with the service.
    """
    @abstractmethod
    def run(self):
        raise NotImplementedError


class AbstractForwarder(ABC):
    """
    Forwards synched data to some other systems so they can sync at their turn.
    """
    @abstractmethod
    def on_controller_appeared(self, event):
        raise NotImplementedError

    @abstractmethod
    def on_controller_disappeared(self, event):
        raise NotImplementedError


class AbstractBackstoreSyncher(ABC):
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


class AbstractDeviceSyncher(ABC):
    @abstractmethod
    def update(self, controller, state, event):
        raise NotImplementedError
