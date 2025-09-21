# STEMI Separation Service

A GPU-accelerated stem separation service using Demucs, designed to run on Vast.ai GPU instances.

## Features

- **GPU Acceleration**: Utilizes CUDA for fast stem separation
- **FastAPI**: Modern, async web framework with automatic API documentation
- **Docker Support**: Containerized for easy deployment
- **Vast.ai Integration**: Built-in support for Vast.ai GPU instances
- **Multiple Stems**: Separates audio into drums, bass, vocals, and other instruments
- **RESTful API**: Easy integration with other services

## Quick Start

### 1. Set up environment

```bash
# Clone and navigate to the project
cd stemi-separation-service

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp env.example .env
# Edit .env with your Vast.ai API key
```

### 2. Run locally (with GPU)

```bash
# Using Docker Compose
docker-compose up --build

# Or run directly
python main.py
```

### 3. Deploy to Vast.ai

```bash
# Deploy to Docker Hub
./scripts/deploy.sh

# Deploy to GitHub Container Registry
./scripts/deploy.sh ghcr.io/your-username

# Deploy with custom tag
./scripts/deploy.sh docker.io/your-username v1.0.0
```

## API Endpoints

### Health Check
- `GET /` - Basic health check
- `GET /health` - Detailed health information including GPU status

### Stem Separation
- `POST /separate` - Upload audio file and separate into stems
  - Parameters:
    - `file`: Audio file (multipart/form-data)
    - `stems`: Comma-separated list of stems (optional, default: "drums,bass,other,vocals")

### File Management
- `GET /download/{job_id}/{stem}` - Download a specific stem
- `GET /jobs/{job_id}` - Get job status and available stems
- `DELETE /jobs/{job_id}` - Delete job and its files

## Usage Examples

### Using curl

```bash
# Upload and separate audio
curl -X POST "http://your-instance-ip:8000/separate" \
  -F "file=@your_audio.wav" \
  -F "stems=drums,vocals"

# Check job status
curl "http://your-instance-ip:8000/jobs/{job_id}"

# Download a stem
curl "http://your-instance-ip:8000/download/{job_id}/drums" -o drums.wav
```

### Using Python

```python
import requests

# Upload and separate
with open("audio.wav", "rb") as f:
    response = requests.post(
        "http://your-instance-ip:8000/separate",
        files={"file": f},
        data={"stems": "drums,vocals"}
    )

result = response.json()
print(f"Job ID: {result['job_id']}")

# Download stems
for stem, path in result['output_files'].items():
    download_url = f"http://your-instance-ip:8000/download/{result['job_id']}/{stem}"
    # Download the file...
```

## Project Structure

```
stemi-separation-service/
├── main.py                    # FastAPI application
├── supabase_integration.py    # Supabase storage integration
├── requirements.txt           # Python dependencies
├── Dockerfile                # Docker configuration
├── env.example               # Environment variables template
├── scripts/
│   ├── deploy.sh             # Deployment script
│   ├── test_client.py        # Test client
│   └── test_supabase.py      # Supabase test
└── README.md                 # This file
```

## Vast.ai Instance Details

Your current instance:
- **Instance ID**: 26101781
- **Public IP**: 50.173.192.54
- **SSH Port**: 41420
- **Service Port**: 8000
- **GPU**: RTX 6000

### Connecting to your instance

```bash
# SSH to your instance
ssh root@50.173.192.54 -p 41030

# Or use the machine copy port
ssh root@50.173.192.54 -p 41999
```

## Docker Commands

### Build image
```bash
docker build -t stemi-separation .
```

### Run container
```bash
docker run --gpus all -p 8000:8000 stemi-separation
```

### Run with volumes
```bash
docker run --gpus all -p 8000:8000 \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/outputs:/app/outputs \
  stemi-separation
```

## Configuration

Environment variables:
- `VAST_API_KEY`: Your Vast.ai API key
- `CUDA_VISIBLE_DEVICES`: GPU device ID (default: 0)
- `HOST`: Service host (default: 0.0.0.0)
- `PORT`: Service port (default: 8000)

## Supported Audio Formats

- WAV
- MP3
- FLAC
- M4A
- OGG

## Requirements

- NVIDIA GPU with CUDA support
- Docker with NVIDIA Container Toolkit
- Python 3.8+
- 4GB+ GPU memory recommended

## Troubleshooting

### GPU not detected
```bash
# Check CUDA availability
python -c "import torch; print(torch.cuda.is_available())"

# Check GPU memory
nvidia-smi
```

### Service not accessible
- Ensure port 8000 is open on your Vast.ai instance
- Check firewall settings
- Verify the service is running: `docker logs stemi-separation`

### Out of memory errors
- Reduce batch size in the code
- Use a smaller model variant
- Ensure sufficient GPU memory

## License

MIT License - see LICENSE file for details.
# stemi
