# filepath: /home/holy/prj/kpi-rover/ecu_sw_bb/src/pc_control/protocol.py

import socket
import struct
import logging
import threading
import time
from typing import Optional, Tuple, List, Dict, Any
from enum import IntEnum

# Set up logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("protocol.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CommandId(IntEnum):
    """Command IDs as defined in the protocol specification"""
    GET_API_VERSION = 0x01
    SET_MOTOR_SPEED = 0x02
    SET_ALL_MOTORS_SPEED = 0x03


class StatusCode(IntEnum):
    """Status codes for responses"""
    OK = 0
    ERROR_INVALID_PARAMETER = 1
    ERROR_HARDWARE_FAILURE = 2
    ERROR_TIMEOUT = 3
    ERROR_NOT_IMPLEMENTED = 4


class RoverCommunication:
    """
    Class to handle communication with the rover controller using TCP protocol.
    Implements Layer 2 of the communication protocol.
    """
    
    def __init__(self, host: str = "localhost", port: int = 5000, api_version: int = 1):
        """
        Initialize the communication class.
        
        Args:
            host (str): Hostname or IP address of the rover controller
            port (int): TCP port number
            api_version (int): Version of the ROS2 driver (1-255)
        """
        self.host = host
        self.port = port
        self.api_version = api_version
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.lock = threading.Lock()  # Add thread lock for socket operations
        self.socket_timeout = 0.5     # Increased base timeout
        self.handshake_timeout = 0.5  # Shorter handshake timeout for quicker retries
        self.connect_timeout = 5.0    # Longer timeout for initial connection
        self.read_timeout = 0.5       # Timeout for regular reads
        self.last_command_time = time.time()
        self.last_successful_command = time.time()
        self.connection_timeout = 2.0  # Reduced timeout for connection checks
        self._total_commands = 0
        self._failed_commands = 0
        logger.info(f"RoverCommunication initialized for {host}:{port}")
    
    def connect(self) -> bool:
        """
        Establish a TCP connection with the rover controller.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Clean up any existing connection
            self._cleanup_connection()
            
            logger.info(f"Connecting to {self.host}:{self.port}")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.socket_timeout)
            self.socket.connect((self.host, self.port))
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            self.connected = True
            
            # Try API version check with quick retries
            for attempt in range(3):
                if attempt > 0:
                    time.sleep(0.1)  # Short delay between retries
                logger.debug(f"API version check attempt {attempt + 1}")
                success, version = self.get_api_version()
                if success:
                    logger.info(f"Connected with API version {version}")
                    return True
            
            logger.error("API version check failed after retries")
            self._cleanup_connection()
            return False
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._cleanup_connection()
            return False

    def disconnect(self) -> None:
        """Close the TCP connection"""
        with self.lock:
            if self.socket:
                try:
                    self.socket.close()
                    logger.info("Socket closed")
                except Exception as e:
                    logger.error(f"Error closing socket: {e}")
                finally:
                    self.socket = None
                    self.connected = False
                    logger.info("Disconnected")
    
    def _check_connection_status(self) -> bool:
        """Check if connection is still alive based on last successful command"""
        if not self.connected or not self.socket:
            return False
        
        # More lenient
        if time.time() - self.last_successful_command > self.connection_timeout:
            logger.warning("Connection appears to be dead - no successful commands recently")
            self.connected = False
            return False
        return True

    def _cleanup_connection(self) -> None:
        """Clean up the socket connection"""
        with self.lock:
            if self.socket:
                try:
                    self.socket.close()
                    logger.info("Socket closed")
                except Exception as e:
                    logger.error(f"Error closing socket: {e}")
                finally:
                    self.socket = None
                    self.connected = False
                    logger.info("Connection cleaned up")
    
    def _send_command(self, command_id: int, payload: bytes = b'') -> bool:
        """Send a command according to protocol format: [command_id (1 byte)][payload (N bytes)]"""
        self._total_commands += 1
        
        if not self.connected or not self.socket:
            self._failed_commands += 1
            return False
        
        try:
            with self.lock:
                packet = bytes([command_id]) + payload
                logger.debug(f"TX [{len(packet)} bytes]: {' '.join([f'{b:02x}' for b in packet])}")
                self.socket.sendall(packet)
                self.last_successful_command = time.time()
                return True
                
        except Exception as e:
            logger.error(f"Send failed: {e}")
            self.connected = False
            self._failed_commands += 1
            return False

    def _read_exact(self, size: int) -> bytes:
        """Read exact number of bytes with timeout."""
        data = b''
        remaining = size
        start_time = time.time()
        
        while remaining > 0:
            try:
                chunk = self.socket.recv(remaining)
                if not chunk:
                    logger.error("Connection closed during read - received 0 bytes")
                    raise ConnectionError("Connection closed during read")
                    
                data += chunk
                remaining -= len(chunk)
                logger.debug(f"Received chunk: {' '.join([f'{b:02x}' for b in chunk])} ({len(chunk)} bytes)")
                
            except socket.timeout:
                elapsed = time.time() - start_time
                logger.error(f"Timeout during read after {elapsed:.3f}s - got {len(data)}/{size} bytes: {' '.join([f'{b:02x}' for b in data])}")
                raise
                
        return data

    def get_api_version(self) -> Tuple[bool, int]:
        """Get the API version from the rover controller."""
        if not self.socket:
            return False, 0

        try:
            # Send version request: [command_id (1 byte)][version (1 byte)]
            packet = bytes([CommandId.GET_API_VERSION, self.api_version])
            logger.debug(f"TX API version request: {packet.hex()}")
            self.socket.sendall(packet)
            
            # Read response: [command_id (1 byte)][version (1 byte)]
            response = self._read_exact(2)
            if len(response) != 2:
                logger.error(f"Incomplete API version response: got {len(response)} bytes")
                return False, 0
                
            cmd_id, version = response
            logger.debug(f"RX API version response: {response.hex()}")
            
            if cmd_id != CommandId.GET_API_VERSION:
                logger.error(f"Wrong response command: 0x{cmd_id:02x}")
                return False, 0
            
            logger.info(f"API version received: {version}")
            self.last_successful_command = time.time()
            return True, version

        except Exception as e:
            logger.error(f"API version check failed: {e}")
            return False, 0

    def set_motor_speed(self, motor_id: int, speed: int) -> bool:
        """Set the speed of a specific motor.
        Args:
            motor_id (int): Motor ID (0-3)
            speed (int): Motor speed in RPM (will be multiplied by 100)
        """
        if not 0 <= motor_id <= 3:
            logger.error(f"Invalid motor ID: {motor_id}, must be 0-3")
            return False
        
        # Multiply RPM by 100 as per protocol
        speed_int = speed * 100
        logger.info(f"Setting motor {motor_id} speed: {speed} RPM ({speed_int} encoded)")
        
        # Format: [command_id (1 byte)][motor_id (1 byte)][speed (4 bytes)]
        # Use little-endian format '<' for x86/ARM compatibility
        payload = struct.pack('<Bi', motor_id, speed_int)
        logger.debug(f"Speed bytes: {' '.join([f'{b:02x}' for b in payload])}")
        return self._send_command(CommandId.SET_MOTOR_SPEED, payload)

    def set_all_motors_speed(self, speeds: List[int]) -> bool:
        """Send speeds for all motors."""
        if len(speeds) != 4:
            return False
        
        try:
            speeds_int = [speed * 100 for speed in speeds]
            logger.debug(f"Raw speeds (RPM): {speeds}")
            logger.debug(f"Encoded speeds (RPM*100): {speeds_int}")
            
            # Pack speeds using to_bytes()
            payload = b''
            for speed in speeds_int:
                # Convert to 4 bytes in big-endian order (MSB first)
                speed_bytes = speed.to_bytes(4, byteorder='big', signed=True)
                payload += speed_bytes
                logger.debug(f"Speed {speed}: bytes={' '.join([f'{b:02x}' for b in speed_bytes])}")
            
            return self._send_command(CommandId.SET_ALL_MOTORS_SPEED, payload)
            
        except Exception as e:
            logger.error(f"Failed to set motor speeds: {e}")
            return False

    def is_connected(self) -> bool:
        """
        Check if the connection to the rover controller is active.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self.connected and self.socket is not None

    def get_command_stats(self) -> Tuple[int, int]:
        """Get total commands sent and number of failed commands.
        
        Returns:
            Tuple[int, int]: (total_commands, failed_commands)
        """
        return (self._total_commands, self._failed_commands)

    def reset_command_stats(self) -> None:
        """Reset command statistics counters."""
        self._total_commands = 0
        self._failed_commands = 0
        logger.info("Command statistics reset")


if __name__ == "__main__":
    # Example usage
    rover = RoverCommunication(host="localhost", port=5000)
    
    if rover.connect():
        # Set speed of individual motors
        rover.set_motor_speed(0, 10)  # Motor 0, 10 RPM
        
        # Set all motors at once
        rover.set_all_motors_speed([10, 15, 10, 15])
        
        rover.disconnect()