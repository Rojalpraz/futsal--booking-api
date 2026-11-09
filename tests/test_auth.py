def test_register_user_success(client):
    # Test creating a new user returns 201 and does not leak password hash
    payload = {
        "email": "player1@gmail.com",
        "full_name": "Test Player",
        "phone_number": "9800000000",
        "password": "securepassword123",
    }
    response = client.post("/api/v1/users/", json=payload)
    data = response.json()

    assert response.status_code == 201
    assert data["email"] == "player1@gmail.com"
    assert "password" not in data  # Ensure hashed password is never returned


def test_login_success(client):
    # Test that a registered user can log in and receives a JWT
    # Register user
    client.post(
        "/api/v1/users/",
        json={
            "email": "player2@gmail.com",
            "full_name": "Player2",
            "phone_number": "9811111111",
            "password": "mysecretpassword",
        },
    )

    # Login (FastAPI OAuth2 uses form-data, not raw JSON)
    login_payload = {
        "username": "player2@gmail.com",
        "password": "mysecretpassword",
    }
    response = client.post("/api/v1/auth/login", data=login_payload)
    data = response.json()

    assert response.status_code == 200
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password(client):
    # Test that invalid passwords return 401 Unauthorized
    # Register user
    client.post(
        "/api/v1/users/",
        json={
            "email": "player3@gmail.com",
            "full_name": "Player3",
            "phone_number": "9822222222",
            "password": "correctpassword",
        },
    )

    # Attempt login with bad password
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "player3@gmail.com", "password": "wrongpassword"},
    )

    assert response.status_code == 401
