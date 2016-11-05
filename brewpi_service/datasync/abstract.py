class AbstractSyncher:
    def on_controller_appeared(self, event):
        raise NotImplementedError

    def on_controller_disappeared(self, event):
        raise NotImplementedError

