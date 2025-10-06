from queue import Queue
from typing import Optional
import threading
from .command import Command

class CommandQueue:
    def __init__(self):
        self._queue = Queue()
        self._lock = threading.Lock()
    
    def push(self, command: Command) -> None:
        with self._lock:
            self._queue.put(command)
    
    def pop(self) -> Optional[Command]:
        try:
            return self._queue.get_nowait()
        except:
            return None
    
    def is_empty(self) -> bool:
        return self._queue.empty()
