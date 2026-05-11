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
    # Photo summary surfaced on every EventOut so list views can render the
    # group photo as the card hero (or a count badge) without an extra
    # roundtrip per event. Full photo list lives at GET /events/{id}/photos.
    group_photo_url: str | None = None
    photo_count: int = 0


class EventPhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_id: int
    uploader_user_id: int | None
    url: str
    caption: str | None
    is_group_photo: bool
    taken_at: datetime | None
    width: int | None
    height: int | None
    created_at: datetime


class EventPhotoUpdate(BaseModel):
    caption: str | None = None
    is_group_photo: bool | None = None


class GalleryPhotoOut(BaseModel):
    """Per-photo entry in the cross-event history gallery.

    Includes the parent event's name + start_date so the frontend can render
    section headers and the "dias" carousel caption without follow-up
    lookups per event.
    """
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_id: int
    event_name: str
    event_start_date: date
    url: str
    caption: str | None
    is_group_photo: bool
    taken_at: datetime | None
    width: int | None
    height: int | None
