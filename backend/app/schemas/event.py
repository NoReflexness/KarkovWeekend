from datetime import date, datetime
from datetime import time as Time

from pydantic import BaseModel, ConfigDict, Field

from app.models.chor import ChorAction, ChorMeal
from app.models.event import EventStatus


class EventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    address: str | None = None
    location_url: str | None = None
    summerhouse_url: str | None = None
    start_date: date
    end_date: date
    bed_count: int | None = Field(default=None, ge=1, le=200)
    host_user_id: int | None = None


class EventUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    address: str | None = None
    location_url: str | None = None
    summerhouse_url: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    bed_count: int | None = Field(default=None, ge=1, le=200)
    host_user_id: int | None = None


class ChorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    meal: ChorMeal
    action: ChorAction
    assignee_user_id: int | None


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    time: Time | None
    created_by_user_id: int | None
    attendee_user_ids: list[int] = []


class EventDayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date: date
    chors: list[ChorOut] = []
    activities: list[ActivityOut] = []
    attendee_user_ids: list[int] = []
    bed_demand: int = 0


class BedDemand(BaseModel):
    bed_count: int | None
    peak: int
    peak_date: date | None


class AttendeeSummary(BaseModel):
    user_id: int
    name: str
    role: str
    family_id: int | None
    family_name: str | None
    profile_picture_url: str | None
    days_attended: int


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    address: str | None
    location_url: str | None
    summerhouse_url: str | None
    start_date: date
    end_date: date
    host_user_id: int | None
    status: EventStatus
    bed_count: int | None
    summerhouse_title: str | None = None
    summerhouse_summary: str | None = None
    summerhouse_image_url: str | None = None
    summerhouse_scraped_at: datetime | None = None
    created_at: datetime
    days: list[EventDayOut] = []
    bed_demand: BedDemand
    attendees: list[AttendeeSummary] = []
