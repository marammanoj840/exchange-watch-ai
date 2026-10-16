import logging
import sys
import io

def setup_logger(name: str = "ExchangeWatch") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        # Wrap stdout stream to safely render UTF-8 Emojis on Windows console
        sys_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        handler = logging.StreamHandler(sys_stdout)
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

logger = setup_logger()
