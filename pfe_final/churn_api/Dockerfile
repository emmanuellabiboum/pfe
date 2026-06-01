FROM python:3.11-slim

WORKDIR /app

# Copy project files
COPY . .

# Expose port
EXPOSE 8001

# Run FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
