"""
Aula MCP - Model Context Protocol implementation for Aula
"""
from .client import AulaClient, AuthenticationError
from .calendar import AulaCalendar
from .data_manager import AulaDataManager
from .models import (
    AulaConfig,
    AulaChild,
    AulaProfile,
    AulaToken,
    AulaCalendarEvent,
    AulaCalendarEventFormatted
)
from .const import Features

__version__ = "0.1.0"

__all__ = [
    'AulaClient',
    'AulaCalendar',
    'AulaDataManager',
    'AulaConfig',
    'AulaChild',
    'AulaProfile',
    'AulaToken',
    'AulaCalendarEvent',
    'AulaCalendarEventFormatted',
    'Features',
    'AuthenticationError'
] 