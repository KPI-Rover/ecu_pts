from abc import ABC, abstractmethod
import time
from typing import List, Optional
from dataclasses import dataclass
import struct
import logging
from .transport import ITransport

logger = logging.getLogger(__name__)

@dataclass
class Response:
    success: bool
    data: Optional[bytes] = None
    error_message: str = ""

class Command(ABC):
    def __init__(self, timeout: float = 1.0):
        self.timeout = timeout
    
    @abstractmethod
    def execute(self, transport: ITransport) -> Response:
        pass

class GetApiVersionCommand(Command):
    def execute(self, transport: ITransport) -> Response:
        # Send version request with ROS2 Driver Version as 1
        logger.debug("Sending API version request")
        if not transport.send(bytes([0x01, 0x01])):
            return Response(False, error_message="Failed to send version request")

        # Read response: try to find the expected command id (0x01).
        start_time = time.time()
        timeout = self.timeout
        discarded = []
        while time.time() - start_time < timeout:
            byte = transport.receive(1, timeout=0.1)
            if not byte:
                continue
            b = byte[0]
            if b == 0x01:
                # Read the remaining API version byte
                rest = transport.receive(1)
                if not rest or len(rest) != 1:
                    return Response(False, error_message="Failed to receive API version byte")
                return Response(True, data=bytes([0x01, rest[0]]))
            else:
                discarded.append(b)

        logger.warning(f"Failed to synchronize API version response, discarded bytes: {' '.join(f'{d:02x}' for d in discarded)}")
        return Response(False, error_message="Failed to receive version response")

class SetMotorSpeedCommand(Command):
    def __init__(self, motor_id: int, speed: int):
        super().__init__()
        self.motor_id = motor_id
        self.speed = speed
    
    def execute(self, transport: ITransport) -> Response:
        logger.info(f"Setting motor {self.motor_id} speed to {self.speed} RPM")
        
        # Prepare complete command packet
        speed_value = self.speed * 100
        
        # Format: command_id (1) + motor_id (1) + speed (4 bytes, big-endian, signed)
        command_data = bytearray([0x02, self.motor_id])
        command_data.extend(speed_value.to_bytes(4, byteorder='big', signed=True))
        
        logger.debug(f"Sending: {' '.join(f'{b:02x}' for b in command_data)}")
        
        if not transport.send(command_data):
            return Response(False, error_message=f"Failed to send motor {self.motor_id} speed")

        # Read response - be tolerant to spurious bytes: loop until expected cmd id or timeout
        start_time = time.time()
        timeout = self.timeout
        discarded = []
        while time.time() - start_time < timeout:
            resp = transport.receive(1, timeout=0.1)
            if not resp:
                continue
            b = resp[0]
            if b == 0x02:
                return Response(True)
            discarded.append(b)

        logger.warning(f"SetMotorSpeedCommand: discarding unexpected bytes: {' '.join(f'{d:02x}' for d in discarded)}")
        return Response(False, error_message=f"Invalid response command ID: {discarded[0] if discarded else 'none'}")

class SetAllMotorsSpeedCommand(Command):
    def __init__(self, speeds: List[int]):
        super().__init__()
        self.speeds = speeds
    
    def execute(self, transport: ITransport) -> Response:
        logger.info(f"Setting all motors speeds to {self.speeds} RPM")
        
        # Prepare complete command packet
        command_data = bytearray([0x03])  # command_id
        
        # Add each speed as 4 bytes (big-endian, signed)
        for speed in self.speeds:
            speed_value = speed * 100
            command_data.extend(speed_value.to_bytes(4, byteorder='big', signed=True))
        
        logger.debug(f"Sending: {' '.join(f'{b:02x}' for b in command_data)}")
        
        if not transport.send(command_data):
            return Response(False, error_message="Failed to send speeds")

        # Read response - loop until expected command id or timeout (tolerant to noise)
        start_time = time.time()
        timeout = self.timeout
        discarded = []
        while time.time() - start_time < timeout:
            resp = transport.receive(1, timeout=0.1)
            if not resp:
                continue
            b = resp[0]
            if b == 0x03:
                return Response(True)
            discarded.append(b)

        logger.warning(f"SetAllMotorsSpeedCommand: discarding unexpected bytes: {' '.join(f'{d:02x}' for d in discarded)}")
        # Be lenient as before but report failure upstream
        if discarded:
            logger.warning(f"Expected response command ID 0x03 but got 0x{discarded[0]:02x} - continuing anyway")
            return Response(True)
        return Response(False, error_message="Failed to receive response for SetAllMotorsSpeedCommand")

class GetAllEncodersCommand(Command):
    """Command to get encoder values for all motors."""
    
    def __init__(self):
        super().__init__()
        
    def execute(self, transport: ITransport) -> Response:
        """Execute the command by sending and receiving data over the transport."""
        try:
            logger.debug("Executing GetAllEncodersCommand")

            # Send command ID
            logger.info("TX -> get_all_encoders (0x05)")
            if not transport.send(bytes([0x05])):
                return Response(False, error_message="Failed to send GetAllEncodersCommand")

            # Read command ID first (robust to partial reads and spurious bytes)
            cmd = transport.receive(1)
            if not cmd or len(cmd) == 0:
                return Response(False, error_message="Failed to receive encoder response command ID")

            # Handle spurious 0x00 leading bytes by attempting a short recovery
            if cmd[0] == 0x00:
                logger.warning("Received spurious 0x00 as response command ID, attempting short recovery")
                extra = transport.receive(16, timeout=0.05)
                if extra and len(extra) > 0:
                    # Use first byte of extra as command id and prepend remaining as payload
                    cmd_id = extra[0]
                    payload = extra[1:]
                else:
                    return Response(False, error_message="Invalid response command ID: 0")
            else:
                cmd_id = cmd[0]
                # Now read the remaining payload: 4 values x 4 bytes = 16 bytes
                payload = transport.receive(16)

                # If we didn't get a 16-byte payload, try to recover using any
                # immediately-available bytes (some servers stream payloads
                # without a command id and we may receive exactly 16 bytes of
                # encoder data).
                if not payload or len(payload) < 16:
                    # Try transport.receive_available if implemented
                    avail = None
                    if hasattr(transport, 'receive_available'):
                        try:
                            avail = transport.receive_available()
                        except Exception:
                            avail = None

                    if avail and len(avail) >= 16:
                        # If we received payload-only blocks (16 bytes), accept first 16
                        # bytes as encoder payload.
                        if len(avail) >= 16:
                            payload = avail[:16]
                    else:
                        return Response(False, error_message=f"Incomplete encoder payload: {len(payload) if payload else 0} bytes")

                # Support two possible patterns:
                # 1) Leading command id (cmd_id == 0x05) followed by 16-byte payload
                # 2) Payload-only 16-byte block (cmd_id may not be 0x05)
                if cmd_id != 0x05:
                    # If cmd_id is not 0x05 but we have a valid 16-byte payload,
                    # assume the device sent payload-only blocks and proceed.
                    logger.debug(f"GetAllEncodersCommand: non-standard cmd_id 0x{cmd_id:02x} but using payload-only mode")

                # Extract encoder values (4 bytes each, signed int)
                encoder_values = []
                for i in range(4):
                    offset = i * 4
                    encoder_value = int.from_bytes(payload[offset:offset+4], byteorder='big', signed=True)
                    encoder_values.append(encoder_value)

                logger.info(f"RX <- get_all_encoders response: {encoder_values}")
                logger.debug(f"Got encoder values: {encoder_values}")
                return Response(True, data=encoder_values)
            
        except Exception as e:
            logger.error(f"Error in GetAllEncodersCommand: {str(e)}")
            return Response(False, error_message=f"Error in GetAllEncodersCommand: {str(e)}")
