# Use an official Python runtime as the base image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy dependency definition file
COPY library.txt .

# Install dependencies without caching to keep image size small
RUN pip install --no-cache-dir -r library.txt

# Copy all project files into the container
COPY . .

# Set default command to run main.py interactively
CMD ["python", "main.py"]