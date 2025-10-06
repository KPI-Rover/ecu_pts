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
        
        self.setup_ui()
        
        # Connect ECU connector to control panel if provided
        if self.ecu_connector_adapter:
            self.control.set_ecu_connector(self.ecu_connector_adapter)
        
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
        splitter.addWidget(self.dashboard)
        
        # Control part (25% height)
        self.control = ControlPanel()
        splitter.addWidget(self.control)
        
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
    
    def on_connection_state_changed(self, connected: bool):
        """Handle ECU connector connection state changes."""
        if hasattr(self, 'control'):
            self.control.on_connection_state_changed(connected)
            
    def on_error_occurred(self, error_message: str):
        """Handle ECU connector errors."""
        if hasattr(self, 'control'):
            self.control.on_error_occurred(error_message)
