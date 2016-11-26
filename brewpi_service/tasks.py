# from celery import Celery
from flask_rq2 import RQ

from .datasync.controlbox import ControlboxSyncher

rq = RQ()

@rq.job
def run_synchers():
    """
    Run an inifite loop to sync data from the controller
    """
    ct = ControlboxSyncher()
    ct.run()
