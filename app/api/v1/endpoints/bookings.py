from datetime import UTC, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Booking, Turf, User
from app.schemas.schemas import (
    BookingCreate,
    BookingResponse,
    BookingUpdate,
    PaginatedBookingResponse,
)

router = APIRouter(prefix="/bookings", tags=["Bookings"])


def _to_utc(dt: datetime) -> datetime:
    # Normalize datetime to timezone-aware UTC.
    return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)


@router.post("/", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    booking_in: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    now_utc = datetime.now(UTC)
    start_utc = _to_utc(booking_in.start_time)
    end_utc = _to_utc(booking_in.end_time)

    # 1.Reject past dates
    if start_utc <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book a slot in the past.",
        )

    # 2.Chronological sequence check
    if end_utc <= start_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking end_time must be after start_time.",
        )

    # Multi-day check (allow ending at midnight of the next day)
    is_same_day = booking_in.start_time.date() == booking_in.end_time.date()
    is_midnight_next_day = (
        booking_in.end_time.date() == booking_in.start_time.date() + timedelta(days=1)
        and booking_in.end_time.time() == time(0, 0)
    )
    if not (is_same_day or is_midnight_next_day):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bookings cannot span across multiple calendar days.",
        )

    # 3. Check turf existence & active state with row lock (prevents double-booking race condition)
    turf = (
        db.query(Turf).filter(Turf.id == booking_in.turf_id).with_for_update().first()
    )

    if not turf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Turf with id {booking_in.turf_id} not found.",
        )
    if not turf.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This turf is currently unavailable for bookings.",
        )

    # 4. Operating hours boundary check (supports midnight closing times)
    booking_start_t = booking_in.start_time.time()
    booking_end_t = booking_in.end_time.time()

    is_valid_start = booking_start_t >= turf.opening_time

    if turf.closing_time == time(0, 0):
        # Turf is open until midnight (24:00)
        is_valid_end = booking_end_t == time(0, 0) or booking_end_t > turf.opening_time
    else:
        # Turf closes before midnight
        is_valid_end = (
            booking_end_t != time(0, 0)
            and turf.opening_time < booking_end_t <= turf.closing_time
        )

    if not (is_valid_start and is_valid_end):
        closing_label = (
            "24:00"
            if turf.closing_time == time(0, 0)
            else turf.closing_time.strftime("%H:%M")
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Booking outside operational hours. "
                f"Turf operates between {turf.opening_time.strftime('%H:%M')} "
                f"and {closing_label}."
            ),
        )

    # 5. Overlap check (existing_start < new_end AND existing_end > new_start)
    overlapping_booking = (
        db.query(Booking)
        .filter(
            Booking.turf_id == booking_in.turf_id,
            Booking.status != "cancelled",
            Booking.start_time < booking_in.end_time,
            Booking.end_time > booking_in.start_time,
        )
        .first()
    )
    if overlapping_booking:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The turf is already booked for this selected time slot.",
        )

    # 6. Calculate total price and save
    duration_hours = (end_utc - start_utc).total_seconds() / 3600.0
    total_price = round(duration_hours * turf.hourly_rate, 2)

    new_booking = Booking(
        user_id=current_user.id,
        turf_id=booking_in.turf_id,
        start_time=booking_in.start_time,
        end_time=booking_in.end_time,
        total_price=total_price,
        status="confirmed",
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    return new_booking


@router.get("/", response_model=PaginatedBookingResponse)
def get_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(
        10, ge=1, le=50, description="Max number of records to return (capped at 50)"
    ),
):
    """Retrieve paginated bookings. Admins view all; standard users view their own[cite: 1]."""
    query = db.query(Booking)

    # Scoping: Regular users only see their own bookings[cite: 1]
    if not current_user.is_admin:
        query = query.filter(Booking.user_id == current_user.id)

    # 1. Count total matching rows before applying pagination limits
    total = query.count()

    # 2. Apply ordering, offset, and limit slice
    bookings = query.order_by(Booking.start_time.desc()).offset(skip).limit(limit).all()

    # 3. Return structured payload
    return PaginatedBookingResponse(
        total=total,
        skip=skip,
        limit=limit,
        data=bookings,
    )


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve a single booking by ID."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found.",
        )
    if booking.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this booking.",
        )
    return booking


@router.patch("/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a booking owned by the user or by an admin."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found.",
        )
    if booking.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel this booking.",
        )
    if booking.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking is already cancelled.",
        )
    # Prevent cancelling matches that have already started or concluded
    if _to_utc(booking.start_time) <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a booking that has already started or concluded.",
        )

    booking.status = "cancelled"
    db.commit()
    db.refresh(booking)
    return booking


@router.patch("/{booking_id}", response_model=BookingResponse)
def reschedule_booking(
    booking_id: int,
    booking_in: BookingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reschedule or resize an existing booking."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with id {booking_id} not found.",
        )

    # 1. Ownership check
    if booking.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this booking.",
        )

    # 2. Cannot modify cancelled bookings
    if booking.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify a cancelled booking.",
        )

    now_utc = datetime.now(UTC)
    new_start_utc = _to_utc(booking_in.start_time)
    new_end_utc = _to_utc(booking_in.end_time)

    # 3. Reject moving to or from past dates
    if _to_utc(booking.start_time) <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify a booking that has already started or concluded.",
        )
    if new_start_utc <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reschedule into the past.",
        )

    # 4. Sequence & single-day checks
    if new_end_utc <= new_start_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking end_time must be after start_time.",
        )

    is_same_day = booking_in.start_time.date() == booking_in.end_time.date()
    is_midnight_next_day = (
        booking_in.end_time.date() == booking_in.start_time.date() + timedelta(days=1)
        and booking_in.end_time.time() == time(0, 0)
    )
    if not (is_same_day or is_midnight_next_day):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bookings cannot span across multiple calendar days.",
        )

    # 5. Lock turf & verify operating hours
    turf = db.query(Turf).filter(Turf.id == booking.turf_id).with_for_update().first()
    if not turf or not turf.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Turf is currently unavailable.",
        )

    booking_start_t = booking_in.start_time.time()
    booking_end_t = booking_in.end_time.time()
    is_valid_start = booking_start_t >= turf.opening_time

    if turf.closing_time == time(0, 0):
        is_valid_end = booking_end_t == time(0, 0) or booking_end_t > turf.opening_time
    else:
        is_valid_end = (
            booking_end_t != time(0, 0)
            and turf.opening_time < booking_end_t <= turf.closing_time
        )

    if not (is_valid_start and is_valid_end):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New slot is outside operational hours.",
        )

    # 6. Overlap check with SELF-EXCLUSION (Booking.id != booking_id)
    overlapping_booking = (
        db.query(Booking)
        .filter(
            Booking.turf_id == booking.turf_id,
            Booking.id
            != booking.id,  # Exclude current booking from colliding with itself
            Booking.status != "cancelled",
            Booking.start_time < booking_in.end_time,
            Booking.end_time > booking_in.start_time,
        )
        .first()
    )
    if overlapping_booking:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The turf is already booked for this selected time slot.",
        )

    # 7. Recalculate duration, price, and commit update
    duration_hours = (new_end_utc - new_start_utc).total_seconds() / 3600.0
    booking.start_time = booking_in.start_time
    booking.end_time = booking_in.end_time
    booking.total_price = round(duration_hours * turf.hourly_rate, 2)

    db.commit()
    db.refresh(booking)
    return booking
