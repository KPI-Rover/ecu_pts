from abc import ABC, abstractmethod
from typing import Optional
import socket
import logging
import time

logger = logging.getLogger(__name__)

class ITransport(ABC):
    @abstractmethod
    def connect(self, host: str, port: int) -> bool:
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        pass
    
    @abstractmethod
    def send(self, data: bytes) -> bool:
        pass
    
    @abstractmethod
    def receive(self, size: int, timeout: float = 1.0) -> Optional[bytes]:
        pass

class TCPTransport(ITransport):
    def __init__(self):
        self._socket = None
        self._connected = False
        self._timeout = 2.0  # Increased timeout to 2.0 seconds
        self._host = None
        self._port = None
    
    def connect(self, host: str, port: int) -> bool:
        try:
            # Clean up any existing socket first
            self.disconnect()
            
            self._host = host
            self._port = port
            
            logger.info(f"Attempting to connect to {host}:{port}...")
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self._timeout)
            
            # Try connecting with a more detailed error message
            try:
                self._socket.connect((host, port))
                # Try a simple test to verify connection is working
                self._socket.settimeout(0.5)
                self._socket.sendall(b'\x01\x01')  # Send API version request
                self._socket.settimeout(self._timeout)  # Reset timeout
            except ConnectionRefusedError:
                logger.error(f"Connection refused to {host}:{port}. Ensure the server is running and the IP/port are correct.")
                return False
            except socket.gaierror:
                logger.error(f"Address resolution error for {host}:{port}. Check if the IP address is valid.")
                return False
            except socket.timeout:
                logger.error(f"Connection to {host}:{port} timed out. Server might be slow or unreachable.")
                return False
            
            self._connected = True
            logger.info(f"Successfully connected to {host}:{port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {host}:{port}: {str(e)}")
            self._connected = False
            self.disconnect()  # Clean up socket on error
            return False
    
    def disconnect(self) -> None:
        if self._socket:
            try:
                self._socket.close()
            except:
                pass
            finally:
                self._socket = None
                self._connected = False
        logger.info("Disconnected")
                
    def is_connected(self) -> bool:
        return self._connected and self._socket is not None
    
    def send(self, data: bytes) -> bool:
        if not self.is_connected():
            logger.error("Cannot send data: not connected")
            return False
            
        try:
            # Add small delay to avoid overwhelming the server
            time.sleep(0.01)
            # Log outgoing data at INFO level so it's visible in normal logs
            try:
                hex_str = ' '.join(f'{b:02x}' for b in data)
            except Exception:
                hex_str = str(data)
            logger.info(f"TX -> {hex_str} ({len(data)} bytes)")
            logger.debug(f"Sending: {hex_str} ({len(data)} bytes)")
            self._socket.sendall(data)
            return True
        except Exception as e:
            logger.error(f"Send error: {str(e)}")
            self._connected = False
            return False
            
    def receive(self, size: int, timeout: float = None) -> Optional[bytes]:
        """Receive exactly size bytes or return None on error."""
        if not self.is_connected():
            logger.error("Cannot receive data: not connected")
            return None
            
        if timeout is None:
            timeout = self._timeout
            
        try:
            # Set socket timeout for this operation
            old_timeout = self._socket.gettimeout()
            self._socket.settimeout(timeout)
            
            # Read exactly size bytes
            data = b''
            bytes_to_read = size
            start_time = time.time()
            
            while bytes_to_read > 0:
                # Check if we've exceeded timeout
                if time.time() - start_time > timeout:
                    logger.error(f"Receive timeout: received {len(data)}/{size} bytes")
                    # Restore original timeout
                    self._socket.settimeout(old_timeout)
                    return None
                    
                chunk = self._socket.recv(bytes_to_read)
                if not chunk:
                    logger.error("Connection closed by peer")
                    self._connected = False
                    self._socket.settimeout(old_timeout)
                    return None
                
                data += chunk
                bytes_to_read -= len(chunk)
                
            # Restore original timeout
            self._socket.settimeout(old_timeout)
            # Log received data at INFO level so it's visible in normal logs
            try:
                hex_str = ' '.join(f'{b:02x}' for b in data)
            except Exception:
                hex_str = str(data)
            logger.info(f"RX <- {hex_str} ({len(data)} bytes)")
            logger.debug(f"Received: {hex_str} ({len(data)} bytes)")

            # Handle possible spurious leading null bytes (0x00) which some
            # servers may send as keep-alive or padding. If we've read a
            # single-byte response and it's 0x00, attempt a short re-read to
            # recover the next available byte and treat that as the response.
            if len(data) == 1 and data[0] == 0x00:
                try:
                    # Try to read up to a few more bytes with a very short timeout
                    self._socket.settimeout(0.05)
                    extra = self._socket.recv(16)
                    if extra:
                        logger.debug(f"Discarding spurious 0x00 and using next byte(s): {' '.join(f'{b:02x}' for b in extra)}")
                        # Return the first byte of the extra data as the single-byte response
                        result = bytes([extra[0]])
                        return result
                except Exception:
                    # If we fail to recover, just return the original data
                    pass
                finally:
                    self._socket.settimeout(old_timeout)
            
            return data
            
        except socket.timeout:
            logger.error("Socket timeout during receive")
            self._socket.settimeout(old_timeout)  # Restore timeout
            return None
        except Exception as e:
            logger.error(f"Receive error: {str(e)}")
            self._connected = False
            return None

    def receive_available(self) -> Optional[bytes]:
        """Return any immediately-available bytes from the socket (non-blocking).

        This is a best-effort helper used by higher-level code to recover
        from protocol stream patterns where payloads may arrive without a
        leading command id. It will attempt a non-blocking recv and return
        whatever bytes are available, or None on error.
        """
        if not self.is_connected():
            return None

        try:
            # Use non-blocking peek to see if data is available
            data = self._socket.recv(4096, socket.MSG_DONTWAIT)
            if data:
                logger.debug(f"receive_available: got {len(data)} bytes: {' '.join(f'{b:02x}' for b in data)}")
                return data
            return b''
        except BlockingIOError:
            return b''
        except Exception as e:
            logger.debug(f"receive_available error: {e}")
            return None