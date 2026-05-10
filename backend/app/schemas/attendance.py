from pydantic import BaseModel


class AttendanceToggle(BaseModel):
    present: bool
    # When given, exactly these users have their presence toggled (after a
    # family-membership check on the backend). When omitted we fall back to
    # the legacy "self + own children" behaviour for callers who haven't been
    # updated to use the family-attendance modal yet.
    user_ids: list[int] | None = None


class BulkAttendance(BaseModel):
    day_ids: list[int]
    present: bool
    user_ids: list[int] | None = None


class AttendanceDayOut(BaseModel):
    event_day_id: int
    attendee_user_ids: list[int]
