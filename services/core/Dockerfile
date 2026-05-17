FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (though this service mainly communicates internally)
EXPOSE 8080

# Run the application
# For now, we'll just keep the container alive for testing
# In a real implementation, this would run the actual service
CMD ["python", "-c", "import time; print('Core service running...'); time.sleep(60)"]