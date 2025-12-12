import sys
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QSplitter
from PyQt6.QtCore import Qt
from control_panel import ControlPanel
from dashboard_panel import DashboardPanel


class MainWindow(QMainWindow):
    def __init__(self, ecu_connector_adapter=None):
        super().__init__()
        self.ecu_connector_adapter = ecu_connector_adapter
        self.setWindowTitle("ECU PTS - Performance Testing Software")
        self.setMinimumSize(1200, 800)
        
        # Create status bar
        self.statusBar().showMessage("Not connected")
        
        self.setup_ui()
        
        # Connect ECU connector to control panel if provided
        if self.ecu_connector_adapter:
            self.control.set_ecu_connector(self.ecu_connector_adapter)
            # Also register adapter with dashboard so tabs can communicate
            if hasattr(self, 'dashboard') and hasattr(self.dashboard, 'set_ecu_connector'):
                self.dashboard.set_ecu_connector(self.ecu_connector_adapter)
            
            # Fix: Use the correct signal name
            self.ecu_connector_adapter.encoderValuesUpdated.connect(self.on_encoder_values_updated)
            self.ecu_connector_adapter.imuValuesUpdated.connect(self.on_imu_values_updated)
        
    def setup_ui(self):
        """Setup the main UI layout with Dashboard and Control parts."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create splitter for Dashboard and Control parts
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Dashboard part (75% height)
        self.dashboard = DashboardPanel()
        self.dashboard.startUdpRequested.connect(self.on_start_udp_requested)
        splitter.addWidget(self.dashboard)
        
        # Control part (25% height)
        self.control = ControlPanel()
        splitter.addWidget(self.control)
        
        # Connect max RPM changes to dashboard
        self.control.maxRpmChanged.connect(self.dashboard.on_max_rpm_changed)
        
        # Set initial sizes explicitly: Dashboard 75%, Control 25%
        # This will be calculated after the window is shown
        splitter.setSizes([600, 200])  # 3:1 ratio
        splitter.setStretchFactor(0, 3)  # Dashboard
        splitter.setStretchFactor(1, 1)  # Control
        
        # Store splitter reference to update sizes on resize
        self.splitter = splitter
        
        layout.addWidget(splitter)
    
    def resizeEvent(self, event):
        """Maintain 75/25 split on window resize."""
        super().resizeEvent(event)
        if hasattr(self, 'splitter'):
            height = self.height()
            dashboard_height = int(height * 0.75)
            control_height = int(height * 0.25)
            # Ensure minimum height for control panel
            if control_height < 180:
                control_height = 180
                dashboard_height = height - control_height
            self.splitter.setSizes([dashboard_height, control_height])
    
    def on_connection_state_changed(self, connected: bool, udp_port: int = None):
        """Handle ECU connector connection state changes."""
        if hasattr(self, 'control'):
            self.control.on_connection_state_changed(connected)
        
        if connected:
            self.udp_port = udp_port
            if udp_port:
                self.statusBar().showMessage(f"Connected to rover, UDP listening on port {udp_port}")
            else:
                self.statusBar().showMessage("Connected to rover")
        else:
            self.udp_port = None
            self.statusBar().showMessage("Disconnected from rover")
            
    def on_error_occurred(self, error_message: str):
        """Handle ECU connector errors."""
        if hasattr(self, 'control'):
            self.control.on_error_occurred(error_message)
        
        self.statusBar().showMessage(f"Error: {error_message}", 5000)
            
    def on_encoder_values_updated(self, encoder_values: list):
        """Handle encoder values updates emitted by adapter.

        The `ECUConnectorAdapter.encoderValuesUpdated` signal emits a single
        `list` containing encoder values. Compute context information (current
        setpoints and time elapsed) and forward to the dashboard's
        `update_chart_data` method.
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"MainWindow.on_encoder_values_updated called with: {encoder_values}")
        
        # Get current setpoints from ECU connector adapter (includes joystick control)
        if hasattr(self, 'ecu_connector_adapter'):
            setpoints = self.ecu_connector_adapter.current_speeds.copy()
        else:
            setpoints = [0, 0, 0, 0]

        # Compute time elapsed in seconds from adapter refresh interval
        time_elapsed = 0.0
        if hasattr(self, 'ecu_connector_adapter') and hasattr(self.ecu_connector_adapter, 'refresh_interval_ms'):
            time_elapsed = self.ecu_connector_adapter.refresh_interval_ms / 1000.0

        logger.info(f"Forwarding to dashboard: setpoints={setpoints}, encoder_values={encoder_values}, time_elapsed={time_elapsed}")
        
        # Forward to dashboard tab if available
        if hasattr(self, 'dashboard'):
            self.dashboard.update_chart_data(setpoints, encoder_values, time_elapsed)
        else:
            logger.warning("MainWindow has no dashboard attribute!")
            
    def on_imu_values_updated(self, imu_data: list):
        """Handle IMU values updates."""
        if hasattr(self, 'dashboard'):
            self.dashboard.update_imu_data(imu_data)

    def on_start_udp_requested(self):
        """Handle request to start UDP server."""
        if not self.ecu_connector_adapter or not hasattr(self, 'udp_port') or not self.udp_port:
            self.statusBar().showMessage("Cannot start UDP: Not connected or no local port")
            return
            
        self.statusBar().showMessage(f"Sending Connect UDP command with port {self.udp_port}...")
        self.ecu_connector_adapter.ecu_connector.connect_udp(self.udp_port)
