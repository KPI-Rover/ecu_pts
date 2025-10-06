import logging

# Setup package-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Only add handlers if they haven't been added yet
if not logger.handlers:
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Add file handler
    file_handler = logging.FileHandler("ecu_connector.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False

from .connector import ECUConnector
from .transport import ITransport, TCPTransport
from .command import Command, Response
from .queue import CommandQueue

__all__ = [
    'ECUConnector',
    'ITransport',
    'TCPTransport',
    'Command',
    'Response',
    'CommandQueue',
    'logger'
]
