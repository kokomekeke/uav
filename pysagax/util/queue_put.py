from queue import Queue
import queue
from typing import Any

def queue_put(q: Queue[Any], data, timeout: float=1, logger = None):
    """
    Tries to put data into q. If it's full, it drops the data.
    """
    try:
        q.put(data, timeout=timeout)
    except queue.Full: 
        if logger is not None:
            logger.warning("Output queue is full, data is dropped")
