"""
This class defines a custom exception class for exceeding the max workers on a machine.
"""

class MaxWorkerError(Exception):
    """
    Raised when the number of workers assigned to `max_workers` exceeds the number of CPU/workers on the machine. 
    """
    pass
