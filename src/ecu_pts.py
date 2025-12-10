import sys
import logging
import socket
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
    
    connectionStateChanged = pyqtSignal(bool)
    errorOccurred = pyqtSignal(str)
    encoderValuesUpdated = pyqtSignal(list)  # New signal for encoder values
    
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
            self.connectionStateChanged.emit(True)
            logger.info(f"Successfully connected to {host}:{port}")
            
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
        self.ecu_connector.disconnect()
        self.connectionStateChanged.emit(False)
        
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
    
    def set_encoder_ticks_per_rev(self, motor_id: int, ticks: int):
        """Set encoder ticks per revolution for a specific motor."""
        if 0 <= motor_id < 4:
            self.encoder_ticks_per_rev[motor_id] = ticks
    
    def get_encoder_ticks_per_rev(self, motor_id: int) -> int:
        """Get encoder ticks per revolution for a specific motor."""
        if 0 <= motor_id < 4:
            return self.encoder_ticks_per_rev[motor_id]
        return 1328  # Default
    
    def calculate_rpm_from_encoder(self, motor_id: int, encoder_value: int, time_interval_ms: int) -> float:
        """Calculate RPM from encoder value change."""
        # This is a simplified calculation
        # In real implementation, you would track previous values and times
        ticks_per_rev = self.encoder_ticks_per_rev[motor_id]
        if ticks_per_rev <= 0:
            return 0.0
        
        # Convert to RPM: (encoder_value / ticks_per_rev) * (60000 / time_interval_ms)
        # This is a placeholder calculation - actual implementation would track delta values
        return (encoder_value / ticks_per_rev) * (60000 / time_interval_ms)


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