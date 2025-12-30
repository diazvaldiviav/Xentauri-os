FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Make startup script executable
RUN chmod +x start.sh

# Expose port
EXPOSE 8080

# Run startup script (runs migrations, then starts app)
CMD ["./start.sh"]
