from abc import abstractmethod, ABC


class AbstractControllerSyncher(ABC):
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
