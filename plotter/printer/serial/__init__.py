"""Marlin-over-serial printer backend.

``transport`` — port abstraction and protocol constants; ``worker`` — the
streaming thread and its process-wide singleton; ``client`` — the
``PrinterBackend`` facade used by the factory.
"""

from plotter.printer.serial.client import SerialClient
from plotter.printer.serial.worker import (
    SerialWorker,
    get_worker,
    peek_worker,
    reset_worker,
    shutdown_worker,
)

__all__ = [
    "SerialClient",
    "SerialWorker",
    "get_worker",
    "peek_worker",
    "reset_worker",
    "shutdown_worker",
]
