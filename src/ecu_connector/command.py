from abc import ABC, abstractmethod
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
        # Send version request
        if not transport.send(bytes([0x01])):
            return Response(False, error_message="Failed to send version request")
        
        # Read response
        data = transport.receive(2)
        if not data or len(data) != 2:
            return Response(False, error_message="Failed to receive version response")
            
        return Response(True, data=data)

class SetMotorSpeedCommand(Command):
    def __init__(self, motor_id: int, speed: int):
        super().__init__()
        self.motor_id = motor_id
        self.speed = speed
    
    def execute(self, transport: ITransport) -> Response:
        logger.info(f"Setting motor {self.motor_id} speed to {self.speed} RPM")
        # Send command ID first
        if not transport.send(bytes([0x02])):
            return Response(False, error_message="Failed to send command ID")
            
        # Send motor_id and speed (multiplied by 100 as per protocol)
        payload = struct.pack('>Bi', self.motor_id, self.speed * 100)
        if not transport.send(payload):
            return Response(False, error_message=f"Failed to send motor {self.motor_id} speed")
            
        return Response(True)

class SetAllMotorsSpeedCommand(Command):
    def __init__(self, speeds: List[int]):
        super().__init__()
        self.speeds = speeds
    
    def execute(self, transport: ITransport) -> Response:
        logger.info(f"Setting all motors speeds to {self.speeds} RPM")
        # Send command ID first
        if not transport.send(bytes([0x03])):
            return Response(False, error_message="Failed to send command ID")
        
        # Pack and send all speeds using big-endian (multiplied by 100 as per protocol)
        payload = b''
        for speed in self.speeds:
            speed_int = speed * 100
            payload += speed_int.to_bytes(4, byteorder='big', signed=True)
            
        if not transport.send(payload):
            return Response(False, error_message="Failed to send speeds")
            
        return Response(True)
