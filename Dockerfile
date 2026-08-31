# Use the official Python 3.12 slim image as the base image.
# The 'slim' variant is much smaller than the standard image, containing only the minimal packages needed to run Python.
FROM python:3.12-slim

# Set the working directory inside the container to /app.
# Any subsequent RUN, CMD, ENTRYPOINT, COPY, and ADD instructions will be executed from this directory.
WORKDIR /app

# Copy the requirements.txt file from your local machine into the container's working directory.
COPY requirements.txt .

# Install the Python dependencies listed in requirements.txt.
# The '--no-cache-dir' flag tells pip not to save downloaded packages locally, which helps keep the final Docker image size small.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project files from your local machine into the container's working directory.
# Files specified in a .dockerignore file will not be copied.
COPY . .

# Set the default command for the container to keep it running idle indefinitely.
# This allows you to manually connect to the container and run individual scripts as needed.
CMD ["tail", "-f", "/dev/null"]
