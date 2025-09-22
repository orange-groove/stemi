# Use RunPod's optimized PyTorch base image for GPU support
FROM runpod/pytorch:2.2.0-py3.10-cuda12.1.1-devel-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=0

# Install additional system dependencies (PyTorch base already has Python)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy RunPod requirements first for better caching
COPY runpod_requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r runpod_requirements.txt

# Copy the RunPod handler and lightweight Supabase client
COPY runpod_handler.py .
COPY supabase_client.py .

# Create directories for uploads and outputs
RUN mkdir -p /app/uploads /app/outputs

# Run the fixed RunPod handler with memory optimizations
CMD ["python", "-u", "runpod_handler.py"]
