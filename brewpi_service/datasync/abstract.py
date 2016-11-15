from abc import abstractmethod

class AbstractControllerSyncher:
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

