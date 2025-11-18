from queue import Queue
import queue
from typing import Any


def queue_put(q: Queue[Any], data, timeout: float = 1, logger=None, message: str = ""):
    """
    Tries to put data into q. If it's full, it drops the data.
    """
    try:
        q.put(data, timeout=timeout)
    except queue.Full:
        if logger is not None:
            logger.warning(" ".join([message, "Output queue is full, data is dropped."]))

def multi_put(queues, data, timeout=0):
    for q in queues:
        try:
            q.put(data, timeout=timeout)
        except queue.Full:
            pass
