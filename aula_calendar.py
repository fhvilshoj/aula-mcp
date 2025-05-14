"""
Calendar functionality for the Aula MCP
"""
import logging
import json
import calendar as py_calendar  # Import the standard library calendar with a different name
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

from client import AulaClient
from models.calendar import (
    AulaCalendarEvent, 
    AulaCalendarEventFormatted,
    CalendarRequestParams
)

_LOGGER = logging.getLogger(__name__)

class AulaCalendar:
    """Class for handling Aula calendar data"""
    
    def __init__(self, client: AulaClient):
        """Initialize the calendar handler
        
        Args:
            client: Authenticated Aula client
        """
        self.client = client
        self.events_by_child = {}
        
    def get_calendar_events(self, child_id: str, days: int = 14) -> List[AulaCalendarEvent]:
        """Get calendar events for a child
        
        Args:
            child_id: ID of the child
            days: Number of days to fetch
            
        Returns:
            List[AulaCalendarEvent]: List of calendar events
        """
        # Convert to string for consistent comparison
        child_id_str = str(child_id)

        # If we already have events for this child, return them
        if child_id_str in self.events_by_child:
            return self.events_by_child[child_id_str]
            
        # Otherwise, fetch new data
        try:
            # First, try to get events from user calendar
            events = self._get_events_from_user_calendar(child_id_str)
            
            # Next, try to get events from main calendar
            main_events = self._get_events_from_main_calendar(child_id_str)
            
            # Combine both event lists
            all_events = events + main_events
            
            # Store for future use
            self.events_by_child[child_id_str] = all_events
            
            # Return all events
            return all_events
        except Exception as e:
            _LOGGER.error(f"Error fetching calendar events for child {child_id_str}: {e}")
            return []
        
    def format_calendar_events(self, events: List[AulaCalendarEvent]) -> List[AulaCalendarEventFormatted]:
        """Format calendar events for display
        
        Args:
            events: List of calendar events
            
        Returns:
            List[AulaCalendarEventFormatted]: List of formatted calendar events
        """
        formatted_events = []
        
        for event in events:
            summary = event.title
            location = None
            if event.primary_resource and event.primary_resource.get("name"):
                location = event.primary_resource.get("name")
                
            # Extract teacher information
            teacher = ""
            if event.lesson and event.lesson.participants:
                is_substitute = False
                
                # Check if there's a substitute teacher
                for participant in event.lesson.participants:
                    if participant.participant_role == "substituteTeacher":
                        teacher = f"VIKAR: {participant.teacher_name}"
                        is_substitute = True
                        break
                        
                # If not a substitute, use the first teacher
                if not is_substitute and event.lesson.participants:
                    try:
                        # First try teacher initials
                        if event.lesson.participants[0].teacher_initials:
                            teacher = event.lesson.participants[0].teacher_initials
                        # Fallback to teacher name
                        elif event.lesson.participants[0].teacher_name:
                            teacher = event.lesson.participants[0].teacher_name
                    except Exception as e:
                        _LOGGER.debug(f"Failed to extract teacher information: {e}")
                        
            # Create formatted event
            formatted_event = AulaCalendarEventFormatted(
                summary=f"{summary}, {teacher}" if teacher else summary,
                start=event.start_date_time,
                end=event.end_date_time,
                location=location,
                teacher=teacher
            )
            
            formatted_events.append(formatted_event)
            
        return formatted_events
        
    def filter_events_by_date_range(
        self, 
        events: List[AulaCalendarEventFormatted], 
        start_date: datetime, 
        end_date: datetime
    ) -> List[AulaCalendarEventFormatted]:
        """Filter events by date range
        
        Args:
            events: List of formatted calendar events
            start_date: Start date
            end_date: End date
            
        Returns:
            List[AulaCalendarEventFormatted]: Filtered list of events
        """
        filtered_events = []
        
        for event in events:
            if event.end > start_date and event.start < end_date:
                filtered_events.append(event)
                
        return filtered_events
        
    def get_events_for_child(
        self, 
        child_id: str, 
        start_date: Optional[datetime] = None, 
        end_date: Optional[datetime] = None,
        days: int = 14
    ) -> List[Dict[str, Any]]:
        """Get all events for a child in a specific time range
        
        Args:
            child_id: ID of the child
            start_date: Optional start date (defaults to now)
            end_date: Optional end date (defaults to now + days)
            days: Number of days to fetch if start/end not provided
            
        Returns:
            List[Dict[str, Any]]: List of formatted calendar events as dicts
        """
        # Make sure child_id is a string
        child_id_str = str(child_id)
        
        # Set default date range if not provided
        if start_date is None:
            start_date = datetime.now()
        if end_date is None:
            end_date = start_date + timedelta(days=days)
            
        # Get or fetch calendar events
        if child_id_str not in self.events_by_child:
            events = self.get_calendar_events(child_id_str, days)
        else:
            events = self.events_by_child[child_id_str]
            
        # Format and filter events
        formatted_events = self.format_calendar_events(events)
        filtered_events = self.filter_events_by_date_range(formatted_events, start_date, end_date)
        
        # Convert to dictionaries for easy serialization
        return [event.model_dump() for event in filtered_events] 