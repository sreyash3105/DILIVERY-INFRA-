import logging
import json
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "file": f"{record.filename}:{record.lineno}",
            "function": record.funcName
        }
        
        # Capture tracebacks
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        # Merge extra context if passed via extra={"extra_ctx": {...}}
        extra_ctx = getattr(record, "extra_ctx", None)
        if extra_ctx and isinstance(extra_ctx, dict):
            log_data.update(extra_ctx)
            
        return json.dumps(log_data)

def setup_logging():
    root_logger = logging.getLogger()
    
    # Clear existing handlers to prevent double logs
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.INFO)
    
    # Ensure uvicorn, standard logging, and libraries output JSON
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy", "EventDispatcher", "NotificationTask", "AnalyticsTask"]:
        l = logging.getLogger(logger_name)
        l.handlers = []
        l.propagate = True

from celery.signals import after_setup_logger, after_setup_task_logger

@after_setup_logger.connect
def setup_celery_logger(logger, *args, **kwargs):
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    h = logging.StreamHandler()
    h.setFormatter(JSONFormatter())
    logger.addHandler(h)
    logger.propagate = False

@after_setup_task_logger.connect
def setup_celery_task_logger(logger, *args, **kwargs):
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    h = logging.StreamHandler()
    h.setFormatter(JSONFormatter())
    logger.addHandler(h)
    logger.propagate = False

