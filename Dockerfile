FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright with Chromium browser and system dependencies
# Required for Sprint 6 visual validation pipeline
RUN playwright install --with-deps chromium

# Copy application
COPY . .

# Make startup script executable
RUN chmod +x start.sh

# Expose port
EXPOSE 8080

# Run startup script (runs migrations, then starts app)
CMD ["./start.sh"]
