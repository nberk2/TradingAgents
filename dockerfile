FROM python:3.13-slim

WORKDIR /app

# Copy requirements and install all dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy the web UI file
COPY web_ui.py .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Expose port for web UI
EXPOSE 5000

# Run the web interface
CMD ["python", "web_ui.py"]
