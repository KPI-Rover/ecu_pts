from abc import ABC, abstractmethod
from typing import Optional
import socket
import logging

logger = logging.getLogger(__name__)

class ITransport(ABC):
    @abstractmethod
    def connect(self, host: str, port: int) -> bool:
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        pass
    
    @abstractmethod
    def send(self, data: bytes) -> bool:
        pass
    
    @abstractmethod
    def receive(self, size: int) -> Optional[bytes]:
        pass

class TCPTransport(ITransport):
    def __init__(self, timeout: float = 0.5):
        self.socket: Optional[socket.socket] = None
        self.timeout = timeout
        self.connected = False
    
    def connect(self, host: str, port: int) -> bool:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((host, port))
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.connected = True
            return True
        except Exception as e:
            logger.error(f"TCP connect failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self) -> None:
        if self.socket:
            try:
                self.socket.close()
            finally:
                self.socket = None
                self.connected = False
    
    def send(self, data: bytes) -> bool:
        if not self.socket or not self.connected:
            return False
        try:
            logger.debug(f"Sending: {' '.join([f'{b:02x}' for b in data])} ({len(data)} bytes)")  # Print hex dump
            self.socket.sendall(data)
            return True
        except Exception as e:
            logger.error(f"TCP send failed: {e}")
            self.connected = False
            return False
    
    def receive(self, size: int) -> Optional[bytes]:
        if not self.socket or not self.connected:
            return None
        try:
            data = self.socket.recv(size)
            if data:
                logger.debug(f"Received: {' '.join([f'{b:02x}' for b in data])} ({len(data)} bytes)")  # Print hex dump
            return data
        except Exception as e:
            logger.error(f"TCP receive failed: {e}")
            self.connected = False
            return None
    
    def is_connected(self) -> bool:
        """Check if transport is connected"""
        return self.connected and self.socket is not None
