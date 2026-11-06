from datetime import UTC, datetime, time

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserBase(BaseModel):
    full_name: str
    email: EmailStr
    phone_number: str


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileResponse(UserResponse):
    total_bookings: int


class UserPasswordUpdate(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8)


class TurfBase(BaseModel):
    name: str
    location: str
    hourly_rate: float
    opening_time: time
    closing_time: time


class TurfCreate(TurfBase):
    pass


class TurfResponse(TurfBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingBase(BaseModel):
    turf_id: int
    start_time: datetime
    end_time: datetime


class BookingCreate(BookingBase):
    pass


class BookingResponse(BookingBase):
    booked_id: int = Field(validation_alias="id")
    user_id: int
    total_price: float
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def compute_completed_status(self):
        now = datetime.now(UTC)
        end_utc = (
            self.end_time if self.end_time.tzinfo else self.end_time.replace(tzinfo=UTC)
        )

        if self.status == "confirmed" and end_utc <= now:
            self.status = "completed"
        return self


class BookingUpdate(BaseModel):
    start_time: datetime
    end_time: datetime


class PaginatedBookingResponse(BaseModel):
    total: int
    skip: int
    limit: int
    data: list[BookingResponse]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SlotItem(BaseModel):
    start_time: datetime
    end_time: datetime
    is_available: bool


class TurfAvailabilityResponse(BaseModel):
    turf_id: int
    date: str
    slots: list[SlotItem]
