import logging

# Setup package-level logger
logger = logging.getLogger(__name__)

# Only add handlers if they haven't been added yet
if not logger.handlers:
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Add file handler
    try:
        file_handler = logging.FileHandler("ecu_connector.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not create log file: {e}")
    
    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False

from .connector import ECUConnector
from .transport import ITransport, TCPTransport
from .command import Command, Response, GetAllEncodersCommand, SetAllMotorsSpeedCommand, SetMotorSpeedCommand
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
