FROM python:3.13-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Gradio for web UI
RUN pip install --no-cache-dir gradio==4.44.0

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
