FROM python:3.11-slim

WORKDIR /app

# Copy the requirements file
COPY backend/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend code
COPY backend ./backend

# Copy the frontend code
COPY frontend ./frontend

# Expose the port the app runs on
EXPOSE 8000

# Move into the backend folder before running
WORKDIR /app/backend

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
