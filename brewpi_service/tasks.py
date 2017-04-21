# from celery import Celery
from flask_rq2 import RQ

# from .datasync.controlbox import ControlboxSyncher
from .datasync.legacy import LegacySyncher
from .datasync.database import DatabaseControllerSyncher

rq = RQ()


@rq.job(timeout=-1)
def run_synchers():
    """
    Run an inifite loop to sync data from the controller
    """

    db_syncher = DatabaseControllerSyncher()

    syncher = LegacySyncher()
    syncher.run()
    # ct = ControlboxSyncher()
    # ct.run()
