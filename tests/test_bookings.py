from datetime import UTC, date, datetime, time, timedelta


def get_auth_token(client, email="booker@gmail.com"):
    # Helper function to register and authenticate a user
    client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "full_name": "Booking User",
            "phone_number": "9833333333",
            "password": "password123",
        },
    )
    res = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "password123"},
    )
    return res.json()["access_token"]


def test_booking_overlap_prevention(client, db_session):
    # 1. Setup: Create a turf directly in the test database
    from app.models.turf import Turf  # Adjust import to your Turf model

    turf = Turf(
        name="Test Pitch",
        location="Zone A",
        hourly_rate=1000.0,
        opening_time=time(6, 0),
        closing_time=time(23, 0),
        is_active=True,
    )
    db_session.add(turf)
    db_session.commit()
    db_session.refresh(turf)

    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Use tomorrow's date to avoid "cannot book past dates" validation
    tomorrow = date.today() + timedelta(days=1)
    slot1_start = datetime.combine(tomorrow, time(18, 0), tzinfo=UTC)
    slot1_end = datetime.combine(tomorrow, time(19, 0), tzinfo=UTC)

    # 2. First Booking: 18:00 to 19:00
    payload_1 = {
        "turf_id": turf.id,
        "start_time": slot1_start.isoformat(),
        "end_time": slot1_end.isoformat(),
    }
    response_1 = client.post("/api/v1/bookings/", json=payload_1, headers=headers)
    assert response_1.status_code == 201

    # 3. Second Booking: 18:30 to 19:30
    slot2_start = datetime.combine(tomorrow, time(18, 30), tzinfo=UTC)
    slot2_end = datetime.combine(tomorrow, time(19, 30), tzinfo=UTC)

    payload_2 = {
        "turf_id": turf.id,
        "start_time": slot2_start.isoformat(),
        "end_time": slot2_end.isoformat(),
    }
    response_2 = client.post("/api/v1/bookings/", json=payload_2, headers=headers)

    # Assert business logic enforced
    assert response_2.status_code == 409
    assert "already booked" in response_2.json()["detail"].lower()
