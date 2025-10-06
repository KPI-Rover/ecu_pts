from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt


class DashboardPanel(QWidget):
    """Dashboard panel for displaying real-time charts and visualizations."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Placeholder for charts
        placeholder = QLabel("Dashboard - Charts will be displayed here")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("QLabel { background-color: #f0f0f0; font-size: 18px; }")
        
        layout.addWidget(placeholder)
