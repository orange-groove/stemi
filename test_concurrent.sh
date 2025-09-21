#!/bin/bash

echo "🧪 Testing concurrent GPU usage..."

# Start 3 concurrent separation requests
echo "Starting request 1..."
curl -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/Users/adamgroves/Downloads/Bush - Letting the Cables Sleep.mp3;type=audio/mpeg" \
  -F "stems=vocals,bass,drums,other" \
  http://50.173.192.54:41218/separate > result1.json &

echo "Starting request 2..."
curl -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/Users/adamgroves/Downloads/Bush - Letting the Cables Sleep.mp3;type=audio/mpeg" \
  -F "stems=vocals,bass" \
  http://50.173.192.54:41218/separate > result2.json &

echo "Starting request 3..."
curl -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/Users/adamgroves/Downloads/Bush - Letting the Cables Sleep.mp3;type=audio/mpeg" \
  -F "stems=drums,other" \
  http://50.173.192.54:41218/separate > result3.json &

echo "⏳ Waiting for all requests to complete..."
wait

echo "📊 Results:"
echo "Request 1:" && cat result1.json | jq .
echo "Request 2:" && cat result2.json | jq .
echo "Request 3:" && cat result3.json | jq .

# Clean up
rm result*.json
