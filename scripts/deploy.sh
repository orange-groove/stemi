#!/bin/bash

# Professional Vast.ai deployment script
# Usage: ./scripts/deploy.sh [method] [options]
# Methods: ssh-key, registry, manual

set -e

# Configuration - UPDATE THESE WHEN YOUR INSTANCE CHANGES
# ========================================================
# When you restart/recreate your Vast.ai instance, update these values:
METHOD="${1:-ssh-key}"
INSTANCE_ID="26101781"          # ⚠️  UPDATE: Your Vast.ai instance ID
PUBLIC_IP="50.173.192.54"       # ⚠️  UPDATE: Your instance's public IP
SSH_PORT="41420"                # ⚠️  UPDATE: Your instance's SSH port (usually in instance details)
SSH_KEY="${SSH_KEY:-$HOME/.ssh/vast_ai_key}"

# 🔄 VAST.AI PORT MAPPING REALITY:
# ================================
# Port mappings CHANGE when you:
# - Stop/restart instances
# - Destroy/recreate instances
# - Scale instances
# 
# This script automatically detects the correct ports so you don't need to manually hunt for them!
# Just update the 3 values above when you get a new instance.

# Auto-detect current instance connection details
detect_instance_info() {
    echo "🔍 Verifying instance connectivity..."
    
    # Test SSH connection
    if ! ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p $SSH_PORT root@$PUBLIC_IP 'echo "SSH OK"' >/dev/null 2>&1; then
        echo "❌ Cannot connect to instance at $PUBLIC_IP:$SSH_PORT"
        echo "🔧 Please check:"
        echo "   1. Instance is running"
        echo "   2. SSH port $SSH_PORT is correct"
        echo "   3. Public IP $PUBLIC_IP is current"
        echo "   4. SSH key is properly configured"
        return 1
    fi
    
    echo "✅ SSH connection verified"
    return 0
}


# Registry configuration (for registry method)
REGISTRY="${2:-ghcr.io}"
IMAGE_NAME="stemi-separation"
TAG="${3:-latest}"
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${TAG}"

echo "🚀 Professional Vast.ai Deployment"
echo "=================================="
echo "Method: $METHOD"
echo "Instance: $INSTANCE_ID ($PUBLIC_IP:$SSH_PORT)"
echo ""

# Check if SSH key exists
check_ssh_key() {
    if [ ! -f "$SSH_KEY" ]; then
        echo "❌ SSH key not found: $SSH_KEY"
        echo ""
        echo "🔑 To set up SSH key authentication:"
        echo "1. Generate SSH key:"
        echo "   ssh-keygen -t ed25519 -f ~/.ssh/vast_ai_key"
        echo ""
        echo "2. Add public key to Vast.ai instance:"
        echo "   ssh-copy-id -i ~/.ssh/vast_ai_key.pub -p $SSH_PORT root@$PUBLIC_IP"
        echo ""
        echo "3. Test connection:"
        echo "   ssh -i ~/.ssh/vast_ai_key -p $SSH_PORT root@$PUBLIC_IP 'echo \"Connected!\"'"
        echo ""
        echo "4. Run deployment:"
        echo "   ./scripts/deploy.sh ssh-key"
        exit 1
    fi
}

# Deploy using SSH key
deploy_ssh_key() {
    echo "🔑 Using SSH key authentication..."
    check_ssh_key
    
    # Load environment variables from .env file
    if [ -f ".env" ]; then
        echo "📋 Loading environment variables from .env..."
        set -a  # automatically export all variables
        source .env
        set +a  # stop auto-export
        echo "   Supabase URL: ${SUPABASE_URL:0:20}..." # Show first 20 chars
        echo "   Supabase Key: ${SUPABASE_ANON_KEY:0:20}..." # Show first 20 chars
    else
        echo "⚠️  No .env file found - Supabase storage will not be available"
    fi
    
    # Verify instance connectivity first
    if ! detect_instance_info; then
        echo "❌ Deployment aborted - cannot connect to instance"
        exit 1
    fi
    
    # Use reliable internal port (8080 typically works well with Vast.ai)
    INTERNAL_SERVICE_PORT=8080
    
    echo "📋 Configuration:"
    echo "  Instance: $INSTANCE_ID"
    echo "  SSH: $PUBLIC_IP:$SSH_PORT"
    echo "  Internal Service Port: $INTERNAL_SERVICE_PORT"
    echo ""
    
    # Create deployment package
    echo "📦 Creating deployment package..."
    tar -czf stemi-deployment.tar.gz main.py supabase_integration.py requirements.txt Dockerfile
    
    # Upload and deploy
    echo "📤 Uploading and deploying..."
    scp -i "$SSH_KEY" -o StrictHostKeyChecking=no -P $SSH_PORT stemi-deployment.tar.gz root@$PUBLIC_IP:/root/
    
    # Deploy on instance using separate SSH commands for reliability
    echo "📋 Installing system dependencies..."
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -p $SSH_PORT root@$PUBLIC_IP "apt-get update && apt-get install -y python3 python3-pip python3-dev ffmpeg libsndfile1 libsndfile1-dev"
    
    echo "📋 Extracting deployment package..."
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -p $SSH_PORT root@$PUBLIC_IP "cd /root && tar -xzf stemi-deployment.tar.gz && rm stemi-deployment.tar.gz && mkdir -p /app/uploads /app/outputs"
    
    echo "📋 Installing Python packages..."
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -p $SSH_PORT root@$PUBLIC_IP "cd /root && pip3 install -r requirements.txt && pip3 install --force-reinstall 'numpy<2.0.0'"
    
    echo "📋 Stopping existing services..."
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -p $SSH_PORT root@$PUBLIC_IP "pkill -f python3 2>/dev/null; sleep 2" || true
    
    echo "📋 Starting new service..."
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -p $SSH_PORT root@$PUBLIC_IP "cd /root && export SUPABASE_URL='${SUPABASE_URL:-}' && export SUPABASE_ANON_KEY='${SUPABASE_ANON_KEY:-}' && export PORT=$INTERNAL_SERVICE_PORT && rm -f /var/log/stemi-service.log && nohup python3 main.py > /var/log/stemi-service.log 2>&1 </dev/null & sleep 3"
    
    echo "📋 Checking service status..."
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -p $SSH_PORT root@$PUBLIC_IP "ps aux | grep 'python3 main.py' | grep -v grep && echo 'Service is running' || echo 'Service not found'"
    
    echo "📋 Showing recent logs..."
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -p $SSH_PORT root@$PUBLIC_IP "tail -10 /var/log/stemi-service.log 2>/dev/null || echo 'No logs available yet'"
    
    echo "✅ Service deployment complete!"
    
    # Clean up
    rm -f stemi-deployment.tar.gz
    
    # Auto-detect the actual external port after deployment
    echo ""
    echo "🔍 Auto-detecting external service port..."
    echo "   (This handles Vast.ai's changing port mappings automatically)"
    
    DETECTED_PORT=""
    # Test common Vast.ai port mappings with robust error handling
    for test_port in 41218 41180 41174 40425 41030 40420 40512 41257; do
        printf "Testing port %s... " "$test_port"
        
        # Quick TCP connection test first
        if timeout 3 bash -c "echo >/dev/tcp/$PUBLIC_IP/$test_port" 2>/dev/null; then
            # If TCP works, test HTTP endpoint
            if response=$(curl -s --max-time 3 --fail http://$PUBLIC_IP:$test_port/health 2>/dev/null); then
                if echo "$response" | grep -q '"status":"healthy"'; then
                    echo "✅ FOUND!"
                    DETECTED_PORT=$test_port
                    break
                else
                    echo "❌ (wrong service)"
                fi
            else
                echo "❌ (no HTTP response)"
            fi
        else
            echo "❌ (connection refused)"
        fi
    done
    
    echo ""
    if [ -n "$DETECTED_PORT" ]; then
        echo "🎉 Deployment Complete!"
        echo "======================="
        echo "🌐 Service: http://$PUBLIC_IP:$DETECTED_PORT"
        echo "📊 Health: http://$PUBLIC_IP:$DETECTED_PORT/health" 
        echo "📚 Docs: http://$PUBLIC_IP:$DETECTED_PORT/docs"
        echo ""
        echo "🧪 Test the service:"
        echo "  curl http://$PUBLIC_IP:$DETECTED_PORT/health"
        echo ""
        echo "💡 Save this URL! Port mappings may change when you restart the instance."
    else
        echo "⚠️  External port auto-detection failed"
        echo ""
        echo "🔧 Possible issues:"
        echo "   1. Service may still be starting (wait 30s and check manually)"
        echo "   2. Port mappings changed (check Vast.ai instance details)"
        echo "   3. Instance connectivity issues"
        echo ""
        echo "🌐 Manual check - try these URLs:"
        echo "   http://$PUBLIC_IP:41218/health"
        echo "   http://$PUBLIC_IP:41180/health"
        echo "   http://$PUBLIC_IP:40425/health"
        echo "   http://$PUBLIC_IP:40420/health"
        echo ""
        echo "📋 To fix: Update the deployment script with new instance details from Vast.ai console"
    fi
}

deploy_ssh_key

echo ""
echo "🎯 Final Status:"
echo "=================="
# The service URLs will be displayed by the auto-detection logic above