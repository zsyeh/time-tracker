from django.apps import AppConfig
import logging

from .logging_filters import RedactLearningShareToken


class DrillConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'drill'
    verbose_name = 'Question drill'

    def ready(self):
        for name in ('django.request', 'django.server', 'gunicorn.access'):
            logger = logging.getLogger(name)
            if not any(isinstance(item, RedactLearningShareToken) for item in logger.filters):
                logger.addFilter(RedactLearningShareToken())
