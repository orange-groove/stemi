# Use RunPod's optimized PyTorch base image for GPU support
FROM runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=0

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    ffmpeg \
    libsndfile1 \
    libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic link for python
RUN ln -s /usr/bin/python3 /usr/bin/python

# Set working directory
WORKDIR /app

# Copy RunPod requirements first for better caching
COPY runpod_requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r runpod_requirements.txt

# Copy the RunPod handler
COPY runpod_handler.py .

# Create directories for uploads and outputs
RUN mkdir -p /app/uploads /app/outputs

# Run the RunPod handler
CMD ["python", "-u", "runpod_handler.py"]
