import sys
import logging
import socket
import threading
import struct
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from main_window import MainWindow
from ecu_connector.connector import ECUConnector
from ecu_connector.transport import TCPTransport
from ecu_connector.command import GetAllEncodersCommand

# Setup module logger
logger = logging.getLogger(__name__)

class ECUConnectorAdapter(QObject):
    """Adapter to bridge ECUConnector with Qt signals for UI integration."""
    
    connectionStateChanged = pyqtSignal(bool, int)  # connected, udp_port
    errorOccurred = pyqtSignal(str)
    encoderValuesUpdated = pyqtSignal(list)  # New signal for encoder values
    imuValuesUpdated = pyqtSignal(list)  # IMU data: [imu_id, packet_num, values...]
    
    def __init__(self, ecu_connector: ECUConnector):
        super().__init__()
        self.ecu_connector = ecu_connector
        self.current_speeds = [0, 0, 0, 0]  # Track current motor speeds
        self.encoder_values = [0, 0, 0, 0]  # Track current encoder values
        self.refresh_interval_ms = 200  # Default 200ms
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timer_timeout)
        self.setup_callbacks()
        self.encoder_ticks_per_rev = [1328, 1328, 1328, 1328]  # Default ticks per revolution
        
        # UDP for IMU data
        self.udp_socket = None
        self.udp_thread = None
        self.udp_running = False
        
    def setup_callbacks(self):
        """Setup callbacks to convert to Qt signals."""
        # Create a wrapper function to pass to ECUConnector
        def encoder_callback(values):
            logger.info(f"Encoder callback invoked with values: {values}")
            self.encoder_values = values
            self.encoderValuesUpdated.emit(values)
            logger.info(f"Emitted encoderValuesUpdated signal with values: {values}")
            
        self.ecu_connector.set_callbacks(
            status_callback=self.on_status_update,
            error_callback=self.on_error_update,
            encoder_callback=encoder_callback
        )
        
    def on_status_update(self, message: str):
        """Handle status updates from ECU connector."""
        if "connected" in message.lower():
            self.connectionStateChanged.emit(True)
        elif "disconnected" in message.lower():
            self.connectionStateChanged.emit(False)
            
    def on_error_update(self, message: str):
        """Handle error updates from ECU connector."""
        self.errorOccurred.emit(message)
        
    def connect_to_rover(self, host: str, port: int) -> bool:
        """Connect to rover and start worker thread."""
        logger.info(f"Attempting connection to {host}:{port}")
        
        # Basic validation
        if not host or not port:
            self.errorOccurred.emit("Invalid host or port")
            return False
            
        # Check if host is reachable before connecting
        try:
            # Try a simple ping with short timeout
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(0.5)
            test_socket.connect((host, port))
            test_socket.close()
        except Exception as error:
            error_message = f"Server at {host}:{port} is not reachable: {str(error)}"
            logger.warning(error_message)
            self.errorOccurred.emit(error_message)
            
            # Capture error message for use in lambda
            error_text = str(error)
            # Offer troubleshooting dialog (will be processed in UI thread)
            QTimer.singleShot(0, lambda: self.show_connection_help(host, port, error_text))
            return False
            
        success = self.ecu_connector.connect(host, port)
        if success:
            self.ecu_connector.start()
            
            # Get local port for UDP
            local_port = self.ecu_connector._transport.get_local_port()
            self.connectionStateChanged.emit(True, local_port)
            logger.info(f"Successfully connected to {host}:{port}")
            
            # Start UDP listener for IMU data
            logger.info(f"Starting UDP listener on local port {local_port}")
            self.start_udp_listener(local_port)
            
            # Start periodic updates
            self.timer.start(self.refresh_interval_ms)
        return success
    
    def show_connection_help(self, host, port, error):
        """Show a helpful message box with connection troubleshooting tips."""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Connection Failed")
        msg.setText(f"Could not connect to {host}:{port}")
        
        # Provide detailed troubleshooting steps
        details = (
            f"Error: {error}\n\n"
            f"Troubleshooting steps:\n"
            f"1. Verify that the server is running at {host}:{port}\n"
            f"2. Check if the host machine is reachable (ping {host})\n"
            f"3. Ensure no firewall is blocking the connection\n"
            f"4. Check if the correct IP and port are specified\n"
            f"5. Verify the server application is listening on {host}:{port}\n"
        )
        msg.setDetailedText(details)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
    
    def disconnect_from_rover(self):
        """Disconnect from rover."""
        self.timer.stop()
        
        if self.is_connected():
            # Send stop command to server (port 0)
            logger.info("Sending stop UDP command to server")
            self.ecu_connector.connect_udp(0)
            
            # Give the worker thread a chance to process the command
            import time
            time.sleep(0.2)
            
        self.stop_udp_listener()
        self.ecu_connector.disconnect()
        self.connectionStateChanged.emit(False, None)
        
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.ecu_connector.is_connected()
        
    def set_motor_speed(self, motor_id: int, speed: int):
        """Set individual motor speed - stores for periodic sending."""
        self.current_speeds[motor_id] = speed
        # Don't send immediately - let the periodic timer handle it
        
    def set_all_motors_speed(self, speeds: list, immediate: bool = False):
        """Set all motor speeds - stores for periodic sending or sends immediately.
        
        Args:
            speeds: List of 4 motor speeds
            immediate: If True, sends command immediately with high priority.
                      If False, stores for periodic sending to avoid queue buildup.
        """
        self.current_speeds = speeds.copy()
        if immediate:
            # Clear any pending commands first to ensure immediate execution
            cleared = self.ecu_connector.clear_queue()
            if cleared > 0:
                logger.info(f"Cleared {cleared} pending commands before emergency stop")
            # Send immediately with highest priority for urgent commands (e.g., STOP)
            logger.info(f"Sending IMMEDIATE high-priority command: {speeds}")
            self.ecu_connector.set_all_motors_speed(speeds, priority=0)
        
    def set_refresh_interval(self, interval_ms: int):
        """Set the refresh interval for periodic updates."""
        self.refresh_interval_ms = interval_ms
        if self.timer.isActive():
            self.timer.setInterval(interval_ms)
    
    def on_timer_timeout(self):
        """Handle timer timeout - send current motor speeds periodically and read encoder values."""
        if self.is_connected():
            # Send motor speeds
            logger.info(f"Timer: sending motor speeds {self.current_speeds}")
            self.ecu_connector.set_all_motors_speed(self.current_speeds)
            
            # Read encoder values after a small delay to allow processing
            logger.debug("Timer timeout: scheduled read_encoder_values in 50ms")
            QTimer.singleShot(50, self.read_encoder_values)
        else:
            logger.warning("Timer fired but not connected, skipping command send")
    
    def read_encoder_values(self):
        """Read encoder values from ECU controller."""
        if self.is_connected():
            logger.debug("Requesting encoder values from ECUConnector")
            # Use the get_all_encoders command from the connector directly
            self.ecu_connector.get_all_encoders()
    
    def start_udp_listener(self, local_port: int):
        """Start UDP listener for IMU data on the given port."""
        if self.udp_running:
            return
        
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind(('0.0.0.0', local_port))
            self.udp_socket.settimeout(0.1)  # Short timeout for Qt integration
            self.udp_running = True
            self.udp_thread = threading.Thread(target=self.udp_listener_loop)
            self.udp_thread.daemon = True
            self.udp_thread.start()
            logger.info(f"Started UDP listener on port {local_port}")
        except Exception as e:
            logger.error(f"Failed to start UDP listener: {e}")
            self.errorOccurred.emit(f"Failed to start UDP listener: {e}")
    
    def udp_listener_loop(self):
        """UDP listener loop for IMU data."""
        while self.udp_running:
            try:
                data, addr = self.udp_socket.recvfrom(1024)
                logger.info(f"Received UDP data from {addr}: {data.hex()}")
                self.parse_imu_packet(data)
            except socket.timeout:
                continue
            except Exception as e:
                if self.udp_running:
                    logger.error(f"UDP listener error: {e}")
    
    def parse_imu_packet(self, data: bytes):
        """Parse IMU packet from UDP data."""
        if len(data) < 3:
            return
        
        imu_id = data[0]
        packet_num = struct.unpack('!H', data[1:3])[0]  # uint16_t network order
        
        values = []
        offset = 3
        while offset + 3 < len(data):
            # Each float is sent as uint32_t in network order
            value_bytes = data[offset:offset+4]
            if len(value_bytes) == 4:
                uint32 = struct.unpack('!I', value_bytes)[0]
                # Convert back to float
                float_value = struct.unpack('f', struct.pack('I', uint32))[0]
                values.append(float_value)
            offset += 4
        
        logger.info(f"Parsed IMU: id={imu_id}, packet={packet_num}, values={values}")
        self.imuValuesUpdated.emit([imu_id, packet_num] + values)
    
    def stop_udp_listener(self):
        """Stop UDP listener."""
        self.udp_running = False
        if self.udp_thread:
            self.udp_thread.join(timeout=1.0)
        if self.udp_socket:
            self.udp_socket.close()
            self.udp_socket = None


class ECUPTSApplication:
    """Main ECU PTS Application class."""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.setup_logging()
        
        # Create ECU connector with TCP transport
        transport = TCPTransport()
        ecu_connector = ECUConnector(transport)
        
        # Create adapter for Qt integration
        self.ecu_connector_adapter = ECUConnectorAdapter(ecu_connector)
        
        # Create main window and connect to ECU connector
        self.main_window = MainWindow(self.ecu_connector_adapter)
        
        # Setup application connections
        self.setup_connections()
        
    def setup_logging(self):
        """Setup application logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('ecu_pts.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("ECU PTS Application initialized")
        
    def setup_connections(self):
        """Setup connections between components."""
        # Connect ECU connector signals to main window
        self.ecu_connector_adapter.connectionStateChanged.connect(
            self.main_window.on_connection_state_changed
        )
        self.ecu_connector_adapter.errorOccurred.connect(
            self.main_window.on_error_occurred
        )
        self.ecu_connector_adapter.encoderValuesUpdated.connect(
            self.main_window.on_encoder_values_updated
        )
        self.ecu_connector_adapter.imuValuesUpdated.connect(
            self.main_window.on_imu_values_updated
        )

    def run(self):
        """Run the application."""
        self.main_window.show()
        return self.app.exec()
        
    def shutdown(self):
        """Clean shutdown of the application."""
        self.logger.info("Shutting down ECU PTS Application")
        if self.ecu_connector_adapter:
            self.ecu_connector_adapter.disconnect_from_rover()


def main():
    """Main entry point for ECU PTS application."""
    app = ECUPTSApplication()
    
    try:
        exit_code = app.run()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        exit_code = 0
    finally:
        app.shutdown()
        
    sys.exit(exit_code)


if __name__ == "__main__":
    main()