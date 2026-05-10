from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ExpenseCreate(BaseModel):
    category_id: int
    amount_cents: int = Field(ge=0, le=100_000_000)
    description: str | None = Field(default=None, max_length=500)
    chor_id: int | None = None


class ExpenseUpdate(BaseModel):
    category_id: int | None = None
    amount_cents: int | None = Field(default=None, ge=0, le=100_000_000)
    description: str | None = Field(default=None, max_length=500)
    chor_id: int | None = None
    paid_by_user_id: int | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_id: int
    category_id: int
    chor_id: int | None
    paid_by_user_id: int
    paid_by_user_name: str | None = None
    amount_cents: int
    description: str | None
    created_at: datetime


class UserShareOut(BaseModel):
    user_id: int
    family_id: int
    paid_cents: int
    share_cents: int
    net_cents: int


class SettlementOut(BaseModel):
    from_family_id: int
    to_family_id: int
    amount_cents: int


class BudgetOut(BaseModel):
    event_id: int
    is_final: bool
    total_cents: int
    per_category_cents: dict[int, int]
    shares: list[UserShareOut]
    settlements: list[SettlementOut]
    family_names: dict[int, str] = {}
