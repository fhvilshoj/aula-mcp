"""
Pydantic models for Aula calendar data
"""
from datetime import datetime
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, validator
import pytz

class AulaParticipant(BaseModel):
    """Model representing a participant in a calendar event"""
    participant_role: str = Field(alias="participantRole")
    teacher_name: Optional[str] = Field(alias="teacherName", default=None)
    teacher_initials: Optional[str] = Field(alias="teacherInitials", default=None)

class AulaLesson(BaseModel):
    """Model representing a lesson in a calendar event"""
    participants: List[AulaParticipant] = []

class AulaCalendarEvent(BaseModel):
    """Model representing a calendar event"""
    title: str
    type: str
    start_date_time: datetime = Field(alias="startDateTime")
    end_date_time: datetime = Field(alias="endDateTime")
    belongs_to_profiles: List[str] = Field(alias="belongsToProfiles")
    primary_resource: Optional[Dict[str, Any]] = Field(alias="primaryResource", default=None)
    lesson: Optional[AulaLesson] = None
    
    @validator("start_date_time", "end_date_time", pre=True)
    def parse_datetime(cls, value):
        """Parse datetime string with timezone information"""
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                # Try without timezone
                dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
                return dt.replace(tzinfo=pytz.UTC)
        return value

class AulaCalendarEventFormatted(BaseModel):
    """Model representing a formatted calendar event ready for display"""
    summary: str
    start: datetime
    end: datetime
    location: Optional[str] = None
    teacher: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class CalendarRequestParams(BaseModel):
    """Model representing calendar request parameters"""
    child_ids: List[str | int]
    start_date: datetime
    end_date: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%d 00:00:00.0000%z")
        } 