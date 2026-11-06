from fastapi import FastAPI

from app.api.v1.endpoints.auth import router as auth
from app.api.v1.endpoints.bookings import router as bookings
from app.api.v1.endpoints.turfs import router as turfs
from app.api.v1.endpoints.users import router as user

app = FastAPI()


app.include_router(turfs, prefix="/api/v1")
app.include_router(user, prefix="/api/v1")
app.include_router(bookings, prefix="/api/v1")
app.include_router(auth, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"message": "Futsal Booking API"}
