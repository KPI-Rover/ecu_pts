import sys
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from main_window import MainWindow
from ecu_connector.connector import ECUConnector
from ecu_connector.transport import TCPTransport


class ECUConnectorAdapter(QObject):
    """Adapter to bridge ECUConnector with Qt signals for UI integration."""
    
    connectionStateChanged = pyqtSignal(bool)
    errorOccurred = pyqtSignal(str)
    
    def __init__(self, ecu_connector: ECUConnector):
        super().__init__()
        self.ecu_connector = ecu_connector
        self.current_speeds = [0, 0, 0, 0]  # Track current motor speeds
        self.refresh_interval_ms = 200  # Default 200ms
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timer_timeout)
        self.setup_callbacks()
        
    def setup_callbacks(self):
        """Setup callbacks to convert to Qt signals."""
        self.ecu_connector.set_callbacks(
            status_callback=self.on_status_update,
            error_callback=self.on_error_update
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
        success = self.ecu_connector.connect(host, port)
        if success:
            self.ecu_connector.start()
            self.connectionStateChanged.emit(True)
            # Start periodic sending
            self.timer.start(self.refresh_interval_ms)
        return success
        
    def disconnect_from_rover(self):
        """Disconnect from rover."""
        self.timer.stop()
        self.ecu_connector.disconnect()
        self.connectionStateChanged.emit(False)
        
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.ecu_connector.is_connected()
        
    def set_motor_speed(self, motor_id: int, speed: int):
        """Set individual motor speed."""
        self.current_speeds[motor_id] = speed
        self.ecu_connector.set_motor_speed(motor_id, speed)
        
    def set_all_motors_speed(self, speeds: list):
        """Set all motor speeds."""
        self.current_speeds = speeds.copy()
        self.ecu_connector.set_all_motors_speed(speeds)
        
    def set_refresh_interval(self, interval_ms: int):
        """Set the refresh interval for periodic updates."""
        self.refresh_interval_ms = interval_ms
        if self.timer.isActive():
            self.timer.setInterval(interval_ms)
            
    def on_timer_timeout(self):
        """Handle timer timeout - send current motor speeds periodically."""
        if self.is_connected():
            self.ecu_connector.set_all_motors_speed(self.current_speeds)


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