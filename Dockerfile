# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Install necessary packages and dependencies
RUN apt-get update && \
    apt-get install -y \
    wget \
    gnupg \
    libnss3-dev \
    libgdk-pixbuf2.0-dev \
    libgtk-3-dev \
    libxss-dev \
    libasound2 \
    libcurl4 \
    libu2f-udev \
    libvulkan1 \
    xdg-utils \
    ffmpeg \
    fonts-liberation \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i google-chrome-stable_current_amd64.deb || apt-get install -f -y && \
    rm google-chrome-stable_current_amd64.deb

# Copy the requirements file into the container
COPY text_files/requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY python_files /usr/src/app/python_files

# Copy .env file into the container, root directory
COPY .env /usr/src/app

# Set the environment variable
ENV PATH /usr/src/app/python_files:$PATH

# Command to run the bot
CMD ["python", "python_files/current_version/main.py"]
