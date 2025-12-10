from queue import Queue, PriorityQueue
from typing import Optional
import threading
from .command import Command

class CommandQueue:
    def __init__(self):
        self._queue = PriorityQueue()
        self._lock = threading.Lock()
        self._counter = 0  # For maintaining FIFO order within same priority
    
    def push(self, command: Command, priority: int = 1) -> None:
        """Push command to queue. Lower priority number = higher priority (0 is highest)."""
        with self._lock:
            # Use counter to maintain FIFO order for same priority
            self._queue.put((priority, self._counter, command))
            self._counter += 1
    
    def pop(self) -> Optional[Command]:
        try:
            _, _, command = self._queue.get_nowait()
            return command
        except:
            return None
    
    def is_empty(self) -> bool:
        return self._queue.empty()
    
    def clear(self) -> int:
        """Clear all pending commands from queue. Returns number of commands cleared."""
        with self._lock:
            count = 0
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                    count += 1
                except:
                    break
            return count
