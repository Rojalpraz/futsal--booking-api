# 1. Use a lightweight official Python runtime
FROM python:3.11-slim

# 2. Prevent Python from buffering stdout/stderr and creating .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Set work directory inside the container
WORKDIR /app

# 4. Install OS-level dependencies required for building C extensions (e.g., psycopg2/argon2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. Leverage Docker layer caching: copy requirements first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy the rest of the application code
COPY . .

# 7. Expose the port Uvicorn will listen on
EXPOSE 8000

# 8. Start Uvicorn bound to 0.0.0.0 (required to receive external traffic)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]