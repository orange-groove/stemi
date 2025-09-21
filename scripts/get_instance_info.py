#!/usr/bin/env python3
"""
Vast.ai Instance Information Fetcher
Automatically detects current port mappings and instance details.
"""

import requests
import sys
import os
import json
from typing import Dict, Optional, Tuple

class VastInstanceDetector:
    def __init__(self, api_key: str, instance_id: str):
        self.api_key = api_key
        self.instance_id = instance_id
        self.base_url = "https://console.vast.ai/api/v0"
        
    def get_instance_info(self) -> Optional[Dict]:
        """Get instance information from Vast.ai API"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"{self.base_url}/instances/{self.instance_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"API Error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Error fetching instance info: {e}")
            return None
    
    def detect_port_mapping(self, target_internal_port: int = 8080) -> Optional[Tuple[str, int, int]]:
        """
        Detect the external port mapping for our service
        Returns: (public_ip, external_port, internal_port)
        """
        instance_info = self.get_instance_info()
        
        if not instance_info:
            return None
            
        try:
            # Extract port mappings
            public_ip = instance_info.get('public_ipaddr')
            port_mappings = instance_info.get('ports', {})
            
            # Look for our target internal port
            for mapping in port_mappings:
                if mapping.get('HostPort') and mapping.get('PrivatePort') == target_internal_port:
                    external_port = int(mapping['HostPort'])
                    return (public_ip, external_port, target_internal_port)
            
            # If target port not found, look for common web ports
            web_ports = [8080, 8000, 8888, 5000, 3000]
            for web_port in web_ports:
                for mapping in port_mappings:
                    if mapping.get('PrivatePort') == web_port:
                        external_port = int(mapping['HostPort'])
                        return (public_ip, external_port, web_port)
            
            # Return first available HTTP-like port
            for mapping in port_mappings:
                private_port = mapping.get('PrivatePort')
                if private_port and private_port > 3000:  # Avoid system ports
                    external_port = int(mapping['HostPort'])
                    return (public_ip, external_port, private_port)
                    
            return None
            
        except Exception as e:
            print(f"Error parsing port mappings: {e}")
            return None

def main():
    # Get parameters
    if len(sys.argv) != 3:
        print("Usage: python3 get_instance_info.py <api_key> <instance_id>")
        print("\nExample:")
        print("python3 get_instance_info.py $VAST_API_KEY 26101781")
        sys.exit(1)
    
    api_key = sys.argv[1]
    instance_id = sys.argv[2]
    
    detector = VastInstanceDetector(api_key, instance_id)
    
    # Get full instance info
    instance_info = detector.get_instance_info()
    if not instance_info:
        print("❌ Failed to get instance information")
        sys.exit(1)
    
    # Detect port mapping
    port_info = detector.detect_port_mapping(8080)  # Try 8080 first
    if not port_info:
        port_info = detector.detect_port_mapping(8000)  # Fall back to 8000
    
    if port_info:
        public_ip, external_port, internal_port = port_info
        print(f"PUBLIC_IP={public_ip}")
        print(f"EXTERNAL_PORT={external_port}")
        print(f"INTERNAL_PORT={internal_port}")
        print(f"SSH_PORT={instance_info.get('ssh_port', 22)}")
        
        # Output for bash sourcing
        print(f"\n# Source this output:")
        print(f"export PUBLIC_IP={public_ip}")
        print(f"export EXTERNAL_SERVICE_PORT={external_port}")
        print(f"export INTERNAL_SERVICE_PORT={internal_port}")
        print(f"export SSH_PORT={instance_info.get('ssh_port', 22)}")
        
    else:
        print("❌ No suitable port mapping found")
        sys.exit(1)

if __name__ == "__main__":
    main()
