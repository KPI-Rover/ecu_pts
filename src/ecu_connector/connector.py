import threading
import logging
import time
from typing import List, Tuple, Callable, Optional

from .transport import ITransport
from .command import Command, GetApiVersionCommand, SetMotorSpeedCommand, SetAllMotorsSpeedCommand, Response, GetAllEncodersCommand
from .queue import CommandQueue

logger = logging.getLogger(__name__)

class ECUConnector:
    """ECU Connector class for managing communication with the ECU.
    
    This class handles the low-level communication with the ECU, including
    sending commands and receiving responses. It also manages the worker
    thread that processes commands in the background.
    """

    def __init__(self, transport: ITransport):
        self._transport = transport
        self._command_queue = CommandQueue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._total_commands = 0
        self._failed_commands = 0
        self._status_callback: Optional[Callable[[str], None]] = None
        self._error_callback: Optional[Callable[[str], None]] = None
        self._encoder_callback: Optional[Callable[[list], None]] = None
        self._lock = threading.Lock()

    def set_callbacks(self, 
                     status_callback: Optional[Callable[[str], None]] = None,
                     error_callback: Optional[Callable[[str], None]] = None,
                     encoder_callback: Optional[Callable[[list], None]] = None) -> None:
        """Set callbacks for status and error notifications"""
        self._status_callback = status_callback
        self._error_callback = error_callback
        self._encoder_callback = encoder_callback

    def _worker_loop(self) -> None:
        consecutive_errors = 0
        while self._running:
            try:
                command = self._command_queue.pop()
                if not command:
                    time.sleep(0.001)  # Reduced to 1ms for faster response
                    consecutive_errors = 0  # Reset error counter on successful idle
                    continue

                self._total_commands += 1
                response = command.execute(self._transport)
                
                if response.success:
                    consecutive_errors = 0  # Reset error counter on success
                    
                    # Handle special case for encoder values
                    if isinstance(command, GetAllEncodersCommand) and response.data:
                        if hasattr(self, '_encoder_callback') and self._encoder_callback:
                            self._encoder_callback(response.data)
                        
                    if self._status_callback:
                        self._status_callback("Command executed successfully")
                else:
                    self._failed_commands += 1
                    consecutive_errors += 1
                    if self._error_callback:
                        self._error_callback(f"Command failed: {response.error_message}")
                
                # If we're seeing too many consecutive errors, try reconnecting
                if consecutive_errors >= 5:
                    logger.warning("Too many consecutive errors, attempting reconnect")
                    if hasattr(self, '_host') and hasattr(self, '_port'):
                        self._transport.disconnect()
                        time.sleep(1)
                        if self._transport.connect(self._host, self._port):
                            logger.info("Reconnection successful")
                            consecutive_errors = 0
                        else:
                            logger.error("Reconnection failed")
                    else:
                        logger.error("Cannot reconnect - host/port not stored")

            except Exception as e:
                logger.error(f"Command execution error: {str(e)}")
                self._failed_commands += 1
                consecutive_errors += 1
                
                if self._error_callback:
                    self._error_callback(f"Command execution error: {str(e)}")
                
                # Short sleep to prevent rapid cycling on persistent errors
                time.sleep(0.1)

    def start(self) -> None:
        """Start worker thread"""
        with self._lock:
            if not self._running:
                self._running = True
                self._worker_thread = threading.Thread(target=self._worker_loop)
                self._worker_thread.daemon = True
                self._worker_thread.start()

    def stop(self) -> None:
        """Stop worker thread"""
        with self._lock:
            self._running = False
            if self._worker_thread:
                self._worker_thread.join(timeout=1.0)
                self._worker_thread = None

    def connect(self, host: str, port: int) -> bool:
        """Connect to ECU at specified host and port"""
        return self._transport.connect(host, port)

    def disconnect(self) -> None:
        """Disconnect from ECU"""
        self.stop()
        self._transport.disconnect()

    def set_motor_speed(self, motor_id: int, speed: int, priority: int = 1) -> None:
        """Queue set motor speed command with optional priority (0=highest)"""
        if not self._running:
            return
        command = SetMotorSpeedCommand(motor_id, speed)
        self._command_queue.push(command, priority)

    def set_all_motors_speed(self, speeds: List[int], priority: int = 1) -> None:
        """Queue set all motors speed command with optional priority (0=highest)"""
        if not self._running or len(speeds) != 4:
            return
        command = SetAllMotorsSpeedCommand(speeds)
        self._command_queue.push(command, priority)

    def is_connected(self) -> bool:
        """Check if transport is connected without sending any command"""
        return self._running and self._transport.is_connected()

    def get_command_stats(self) -> Tuple[int, int]:
        """Get the statistics of sent commands"""
        return (self._total_commands, self._failed_commands)

    def reset_command_stats(self) -> None:
        """Reset the command statistics"""
        with self._lock:
            self._total_commands = 0
            self._failed_commands = 0

    def get_all_encoders(self) -> None:
        """Queue get all encoders command."""
        if not self._running:
            return
        from .command import GetAllEncodersCommand
        command = GetAllEncodersCommand()
        logger.debug("Queueing GetAllEncodersCommand")
        self._command_queue.push(command)
    
    def clear_queue(self) -> int:
        """Clear all pending commands from queue. Returns number of commands cleared."""
        count = self._command_queue.clear()
        if count > 0:
            logger.info(f"Cleared {count} pending commands from queue")
        return count