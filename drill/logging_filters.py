"""Keep bearer URLs out of Django/Gunicorn application log records."""
import logging
import re

TOKEN_PATH = re.compile(r'(/share/learning/)[A-Za-z0-9_-]{43}(?=/|\?|$)')


class RedactLearningShareToken(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        replacement = TOKEN_PATH.sub(r'\1<redacted>', message)
        if replacement != message:
            record.msg = replacement
            record.args = ()
        return True
