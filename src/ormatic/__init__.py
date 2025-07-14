__version__ = "1.1.5"

import logging
import sys

# Configure default logging for all loggers in the package
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Get the package logger
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Configure all module loggers
for module_name in ['dao', 'ormatic', 'sqlalchemy_generator']:
    module_logger = logging.getLogger(f"{__name__}.{module_name}")
    module_logger.addHandler(handler)
    module_logger.setLevel(logging.INFO)
