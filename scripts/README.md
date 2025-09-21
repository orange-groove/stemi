# Scripts

## deploy.sh
Main deployment script for Vast.ai instances.

```bash
# Deploy to Docker Hub
./scripts/deploy.sh

# Deploy to GitHub Container Registry
./scripts/deploy.sh ghcr.io/your-username

# Deploy with custom tag
./scripts/deploy.sh docker.io/your-username v1.0.0
```

## test_client.py
Test client for the STEMI separation service.

```bash
# Test health endpoint
python scripts/test_client.py --url http://your-instance-ip:8000

# Test with sample audio
python scripts/test_client.py --url http://your-instance-ip:8000 --create-test
```

## test_supabase.py
Test Supabase integration.

```bash
# Test Supabase storage
python scripts/test_supabase.py
```
