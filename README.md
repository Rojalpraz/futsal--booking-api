# Futsal Turf Booking API

[![CI Pipeline](https://github.com/Rojalpraz/futsal--booking-api/actions/workflows/ci.yml/badge.svg)](https://github.com/Rojalpraz/futsal--booking-api/actions/workflows/ci.yml)

---

## Features

- **Authentication & RBAC:** Secure JWT-based authentication (OAuth2 password flow) with role-based access control for customers and admins.
- **Conflict-Free Bookings:** Enforces database-level locking (`SELECT ... FOR UPDATE`) and temporal overlap validation to eliminate double-booking race conditions.
- **Dynamic Pricing:** Calculates reservation totals on the server based on slot duration and individual turf hourly rates.
- **Containerized Architecture:** Fully dockerized services (Web API + PostgreSQL) with automated health checks, isolated networking, and persistent volumes.
- **Automated Testing & CI:** Pytest suite using an isolated in-memory SQLite database runner, verified automatically on every push via GitHub Actions.

---

## Tech Stack

- **Framework:** FastAPI
- **Language:** Python 3.11
- **Database:** PostgreSQL
- **ORM & Migrations:** SQLAlchemy, Alembic
- **Testing:** Pytest, HTTPX
- **DevOps:** Docker, Docker Compose, GitHub Actions

---

## Getting Started

### Prerequisites

Ensure you have [Docker](https://docs.docker.com/get-docker/) and Docker Compose installed on your system.

### 1. Clone the Repository

```bash
git clone [https://github.com/Rojalpraz/futsal--booking-api.git](https://github.com/Rojalpraz/futsal--booking-api.git)
cd futsal--booking-api
```
