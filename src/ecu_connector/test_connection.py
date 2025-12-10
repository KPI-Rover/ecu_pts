#!/usr/bin/env python3
"""
Test script to validate connection to the ECU server
"""
import sys
import logging
import socket
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def test_basic_connection(host, port):
    """Test basic TCP socket connection"""
    logger.info(f"Testing basic connection to {host}:{port}...")
    
    try:
        # Create socket and connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect((host, port))
        logger.info("Connected successfully!")
        
        # Test API version request
        logger.info("Sending API version request...")
        sock.sendall(b'\x01\x01')
        
        # Receive response
        resp = sock.recv(2)
        if resp:
            logger.info(f"Received response: {' '.join(f'{b:02x}' for b in resp)}")
        else:
            logger.error("No response received")
        
        # Close socket
        sock.close()
        logger.info("Connection test completed")
        return True
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False

def test_protocol(host, port):
    """Test protocol implementation"""
    logger.info(f"Testing protocol with {host}:{port}...")
    
    try:
        # Create socket and connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect((host, port))
        
        # Test commands
        test_commands = [
            # API Version
            {
                "name": "get_api_version",
                "data": b'\x01\x01',
                "response_len": 2
            },
            # Set motor speed (motor 0, 50 RPM)
            {
                "name": "set_motor_speed",
                "data": b'\x02\x00' + (5000).to_bytes(4, byteorder='big', signed=True),
                "response_len": 1
            },
            # Get all encoders
            {
                "name": "get_all_encoders",
                "data": b'\x05',
                "response_len": 17
            },
            # Set all motors speed (10, 20, 30, 40 RPM)
            {
                "name": "set_all_motors_speed",
                "data": b'\x03' + 
                       (1000).to_bytes(4, byteorder='big', signed=True) + 
                       (2000).to_bytes(4, byteorder='big', signed=True) + 
                       (3000).to_bytes(4, byteorder='big', signed=True) + 
                       (4000).to_bytes(4, byteorder='big', signed=True),
                "response_len": 1
            }
        ]
        
        for cmd in test_commands:
            logger.info(f"Testing command: {cmd['name']}")
            logger.debug(f"Sending: {' '.join(f'{b:02x}' for b in cmd['data'])}")
            
            # Send command
            sock.sendall(cmd['data'])
            
            # Small delay to avoid overwhelming the server
            time.sleep(0.1)
            
            # Receive response
            try:
                resp = sock.recv(cmd['response_len'])
                if resp:
                    logger.info(f"Received: {' '.join(f'{b:02x}' for b in resp)}")
                else:
                    logger.error("No response received")
            except socket.timeout:
                logger.error("Response timeout")
        
        # Close socket
        sock.close()
        logger.info("Protocol test completed")
        return True
    except Exception as e:
        logger.error(f"Protocol test failed: {e}")
        return False

def test_problem_commands(host, port):
    """Test problematic commands specifically."""
    logger.info(f"Testing problematic commands with {host}:{port}...")
    
    try:
        # Create socket and connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        sock.connect((host, port))
        
        # Test set_all_motors_speed with the exact values causing issues
        motor_speeds = [0, 76, 0, 0]
        logger.info(f"Testing set_all_motors_speed with values {motor_speeds}...")
        
        # Create command data
        command_data = bytearray([0x03])  # command_id
        for speed in motor_speeds:
            speed_value = speed * 100
            command_data.extend(speed_value.to_bytes(4, byteorder='big', signed=True))
            
        logger.debug(f"Sending: {' '.join(f'{b:02x}' for b in command_data)}")
        sock.sendall(command_data)
        
        # Small delay
        time.sleep(0.1)
        
        # Receive response
        try:
            resp = sock.recv(1)
            if resp:
                logger.info(f"Received: {' '.join(f'{b:02x}' for b in resp)}")
                # Check if the response is the expected 0x03
                if resp[0] != 0x03:
                    logger.warning(f"Expected response ID 0x03 but got 0x{resp[0]:02x}")
            else:
                logger.error("No response received")
        except socket.timeout:
            logger.error("Response timeout")
        
        # Close socket
        sock.close()
        logger.info("Problem command test completed")
        return True
    except Exception as e:
        logger.error(f"Problem command test failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <host> <port>")
        sys.exit(1)
    
    host = sys.argv[1]
    port = int(sys.argv[2])
    
    # Run tests
    if test_basic_connection(host, port):
        test_protocol(host, port)
        test_problem_commands(host, port)
