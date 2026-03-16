# 1. Using the slim Python 3.12.9 image
FROM python:3.12.9-slim

# 2. Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Setup user early
RUN useradd -m fastapiuser
WORKDIR /app
RUN mkdir -p /app/artifacts && chown fastapiuser:fastapiuser /app/artifacts

# 4. Install dependencies (using the cache mount from above)
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# 5. Copy files AND change ownership in ONE step
# This prevents a massive, slow "chown" layer later
COPY --chown=fastapiuser:fastapiuser . .

USER fastapiuser

# 6. Expose the port FastAPI usually runs on
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
