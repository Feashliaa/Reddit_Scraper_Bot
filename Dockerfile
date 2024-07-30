# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the requirements file into the container
COPY text_files/requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies
RUN apt-get update && \
    apt-get install -y \
    libnss3-dev \
    libgdk-pixbuf2.0-dev \
    libgtk-3-dev \
    libxss-dev \
    libasound2 \
    libcurl4 \
    libu2f-udev \
    libvulkan1 \
    xdg-utils \
    wget \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i google-chrome-stable_current_amd64.deb && \
    apt-get install -f && \
    rm google-chrome-stable_current_amd64.deb

# Copy the rest of the application code into the container
COPY python_files /usr/src/app/python_files
COPY .env ./

# Ensure the Chrome driver is available (if needed, install with webdriver-manager in requirements)
# Note: If using undetected-chromedriver, it should handle Chrome driver installation itself.

# Set environment variables
ENV PATH /usr/src/app:$PATH

# Command to run the bot
CMD ["python", "python_files/main.py"]
