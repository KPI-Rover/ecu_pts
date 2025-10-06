import threading
import logging
import time
from typing import List, Tuple, Callable, Optional

from .transport import ITransport
from .command import Command, GetApiVersionCommand, SetMotorSpeedCommand, SetAllMotorsSpeedCommand, Response
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
        self._lock = threading.Lock()

    def set_callbacks(self, 
                     status_callback: Optional[Callable[[str], None]] = None,
                     error_callback: Optional[Callable[[str], None]] = None) -> None:
        """Set callbacks for status and error notifications"""
        self._status_callback = status_callback
        self._error_callback = error_callback

    def _worker_loop(self) -> None:
        while self._running:
            try:
                command = self._command_queue.pop()
                if not command:
                    time.sleep(0.01)  # Prevent busy waiting
                    continue

                self._total_commands += 1
                response = command.execute(self._transport)
                
                if response.success:
                    if self._status_callback:
                        self._status_callback("Command executed successfully")
                else:
                    self._failed_commands += 1
                    if self._error_callback:
                        self._error_callback(f"Command failed: {response.error_message}")

            except Exception as e:
                self._failed_commands += 1
                if self._error_callback:
                    self._error_callback(f"Command execution error: {str(e)}")

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

    def set_motor_speed(self, motor_id: int, speed: int) -> None:
        """Queue set motor speed command"""
        if not self._running:
            return
        command = SetMotorSpeedCommand(motor_id, speed)
        self._command_queue.push(command)

    def set_all_motors_speed(self, speeds: List[int]) -> None:
        """Queue set all motors speed command"""
        if not self._running or len(speeds) != 4:
            return
        command = SetAllMotorsSpeedCommand(speeds)
        self._command_queue.push(command)

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