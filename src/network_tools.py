import socket
import subprocess
import platform
import logging
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)

def check_server_availability(host: str, port: int, timeout: float = 1.0) -> Tuple[bool, str]:
    """
    Check if a server is available at the given host and port.
    
    Args:
        host: The hostname or IP address
        port: The port number
        timeout: Connection timeout in seconds
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Create a socket and try to connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True, f"Server is available at {host}:{port}"
    except socket.timeout:
        return False, f"Connection to {host}:{port} timed out"
    except ConnectionRefusedError:
        return False, f"Connection to {host}:{port} refused - no service is running on this port"
    except socket.gaierror:
        return False, f"Could not resolve hostname: {host}"
    except Exception as e:
        return False, f"Error connecting to {host}:{port}: {str(e)}"

def ping_host(host: str, count: int = 4) -> Tuple[bool, str]:
    """
    Ping a host to check if it's reachable.
    
    Args:
        host: The hostname or IP address
        count: Number of ping packets to send
        
    Returns:
        Tuple of (success, message)
    """
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    command = ['ping', param, str(count), host]
    
    try:
        output = subprocess.check_output(command, universal_newlines=True)
        return True, f"Host {host} is reachable:\n{output}"
    except subprocess.CalledProcessError:
        return False, f"Host {host} is not reachable via ping"
    except Exception as e:
        return False, f"Error pinging host {host}: {str(e)}"

def get_local_network_info() -> Dict[str, Any]:
    """
    Get information about the local network.
    
    Returns:
        Dictionary with network information
    """
    info = {}
    
    try:
        # Get hostname
        info['hostname'] = socket.gethostname()
        
        # Get IP addresses
        info['ip_addresses'] = []
        addrs = socket.getaddrinfo(socket.gethostname(), None)
        for addr in addrs:
            if addr[0] == socket.AF_INET:  # IPv4
                ip = addr[4][0]
                if not ip.startswith('127.'):  # Skip loopback
                    info['ip_addresses'].append(ip)
    except Exception as e:
        logger.error(f"Error getting network info: {str(e)}")
        
    return info

def run_network_diagnostics(host: str, port: int) -> str:
    """
    Run comprehensive network diagnostics.
    
    Args:
        host: The hostname or IP address
        port: The port number
        
    Returns:
        Diagnostic report as a string
    """
    report = ["Network Diagnostics Report", "========================"]
    
    # Local network info
    report.append("\nLocal Network Information:")
    local_info = get_local_network_info()
    report.append(f"Hostname: {local_info.get('hostname', 'Unknown')}")
    report.append(f"IP Addresses: {', '.join(local_info.get('ip_addresses', ['Unknown']))}")
    
    # Ping test
    report.append("\nPing Test:")
    ping_success, ping_msg = ping_host(host)
    report.append(ping_msg)
    
    # Port test
    report.append("\nPort Test:")
    port_success, port_msg = check_server_availability(host, port)
    report.append(port_msg)
    
    return "\n".join(report)
