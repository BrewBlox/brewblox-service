from celery import Celery

from brewpi_service import app

from .datasync.controlbox import ControlboxSyncher


def make_celery(app):
    celery = Celery(app.import_name,
                    backend=app.config['CELERY_RESULT_BACKEND'],
                    broker=app.config['CELERY_BROKER_URL'])
    celery.conf.update(app.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask
    return celery


celery = make_celery(app)


@celery.task
def run_synchers():
    """
    Run an inifite loop to sync data from the controller
    """
    ct = ControlboxSyncher()
    ct.run()
