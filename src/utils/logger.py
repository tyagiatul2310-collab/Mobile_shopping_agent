"""Logging utilities with timing support."""
import logging
import time
import functools
from typing import Callable, Any
from pathlib import Path


def setup_logging(log_level: str = "INFO", log_file: str = "logs/app.log") -> logging.Logger:
    """Setup logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        
    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),  # Also log to console
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Level: {log_level}, File: {log_file}")
    return logger


def log_function_call(func: Callable) -> Callable:
    """Decorator to log function calls with timing information.
    
    Usage:
        @log_function_call
        def my_function(arg1, arg2):
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        
        # Get function name and class name if method
        func_name = func.__name__
        if args and hasattr(args[0], '__class__'):
            class_name = args[0].__class__.__name__
            full_name = f"{class_name}.{func_name}"
        else:
            full_name = func_name
        
        # Log function entry
        args_str = ", ".join([str(arg)[:50] for arg in args[1:]])  # Skip self
        kwargs_str = ", ".join([f"{k}={str(v)[:50]}" for k, v in kwargs.items()])
        params = ", ".join(filter(None, [args_str, kwargs_str]))
        
        logger.info(f"Calling {full_name}({params})")
        
        # Time the function
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            
            # Log success with timing
            result_preview = str(result)[:100] if result is not None else "None"
            logger.info(
                f"Completed {full_name} in {elapsed_time:.4f}s | Result: {result_preview}"
            )
            return result
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(
                f"Error in {full_name} after {elapsed_time:.4f}s | Exception: {type(e).__name__}: {str(e)}",
                exc_info=True
            )
            raise
    
    return wrapper


def log_timing(operation_name: str = None):
    """Context manager for timing operations.
    
    Usage:
        with log_timing("Database query"):
            result = db.query(sql)
    """
    class TimingContext:
        def __init__(self, name: str):
            self.name = name or "Operation"
            self.logger = logging.getLogger(__name__)
            self.start_time = None
        
        def __enter__(self):
            self.start_time = time.time()
            self.logger.info(f"Starting: {self.name}")
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            elapsed_time = time.time() - self.start_time
            if exc_type is None:
                self.logger.info(f"Completed: {self.name} in {elapsed_time:.4f}s")
            else:
                self.logger.error(
                    f"Failed: {self.name} after {elapsed_time:.4f}s | "
                    f"Exception: {exc_type.__name__}: {str(exc_val)}",
                    exc_info=True
                )
            return False  # Don't suppress exceptions
    
    return TimingContext(operation_name)


# Get logger instance
def get_logger(name: str = None) -> logging.Logger:
    """Get a logger instance for a module.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name or __name__)

