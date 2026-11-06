from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin_user
from app.db.session import get_db
from app.models.booking import Booking
from app.models.turf import Turf
from app.models.user import User
from app.schemas.schemas import (
    SlotItem,
    TurfAvailabilityResponse,
    TurfCreate,
    TurfResponse,
)

router = APIRouter(prefix="/turfs", tags=["Turfs"])


@router.post("/", response_model=TurfResponse, status_code=status.HTTP_201_CREATED)
def create_turf(
    turf_in: TurfCreate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
):
    """Admin can only create new turf"""
    new_turf = Turf(**turf_in.model_dump())
    db.add(new_turf)
    db.commit()
    db.refresh(new_turf)
    return new_turf


@router.get("/", response_model=list[TurfResponse])
def list_turfs(db: Session = Depends(get_db)):
    """Everyone can view all operational turfs."""
    return db.query(Turf).filter(Turf.is_active == True).all()


@router.get("/{turf_id}", response_model=TurfResponse)
def get_turf_by_id(turf_id: int, db: Session = Depends(get_db)):
    """everyone can retrieve specific turf details."""
    turf = db.query(Turf).filter(Turf.id == turf_id).first()
    if not turf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Turf with id {turf_id} not found",
        )
    return turf


@router.patch("/{turf_id}/toggle-status", response_model=TurfResponse)
def toggle_turf_status(
    turf_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
):
    """Admin can only toggle the status of a turf."""
    turf = db.query(Turf).filter(Turf.id == turf_id).first()
    if not turf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Turf with id {turf_id} not found",
        )
    turf.is_active = not turf.is_active
    db.commit()
    db.refresh(turf)
    return turf


@router.get("/{turf_id}/availability", response_model=TurfAvailabilityResponse)
def get_turf_availability(
    turf_id: int,
    target_date: date,
    db: Session = Depends(get_db),
):
    """Public: Query available 1-hour slots for a specific turf and date."""
    turf = db.query(Turf).filter(Turf.id == turf_id).first()
    if not turf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Turf with id {turf_id} not found",
        )

    # Fetch all confirmed bookings for this turf on the target date
    day_start = datetime.combine(target_date, time(0, 0), tzinfo=UTC)
    day_end = day_start + timedelta(days=1)

    existing_bookings = (
        db.query(Booking)
        .filter(
            Booking.turf_id == turf_id,
            Booking.status != "cancelled",
            Booking.start_time < day_end,
            Booking.end_time > day_start,
        )
        .all()
    )

    # Determine turf opening and closing hours for the day
    start_dt = datetime.combine(target_date, turf.opening_time, tzinfo=UTC)
    if turf.closing_time == time(0, 0):
        # Open until midnight (start of next day)
        end_dt = datetime.combine(
            target_date + timedelta(days=1), time(0, 0), tzinfo=UTC
        )
    else:
        end_dt = datetime.combine(target_date, turf.closing_time, tzinfo=UTC)

    # Generate 1-hour slots and evaluate collisions
    slots: list[SlotItem] = []
    current_slot_start = start_dt

    while current_slot_start < end_dt:
        current_slot_end = current_slot_start + timedelta(hours=1)

        # Check if slot overlaps with any confirmed booking
        is_booked = any(
            (
                b.start_time.astimezone(UTC)
                if b.start_time.tzinfo
                else b.start_time.replace(tzinfo=UTC)
            )
            < current_slot_end
            and (
                b.end_time.astimezone(UTC)
                if b.end_time.tzinfo
                else b.end_time.replace(tzinfo=UTC)
            )
            > current_slot_start
            for b in existing_bookings
        )

        slots.append(
            SlotItem(
                start_time=current_slot_start,
                end_time=current_slot_end,
                is_available=not is_booked,
            )
        )
        current_slot_start = current_slot_end

    return TurfAvailabilityResponse(
        turf_id=turf_id,
        date=str(target_date),
        slots=slots,
    )
