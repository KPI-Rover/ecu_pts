import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QSlider, QLabel, QGridLayout, QLineEdit, QFormLayout, QPushButton,
    QMessageBox, QSpinBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5 import QtGui

from PyQt5.QtGui import QPainter, QColor
from ecu_connector import ECUConnector, TCPTransport
from ecu_connector import logger as ecu_logger

# Setup logging with more detailed format
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
ui_logger = logging.getLogger("ui_control")

class SliderWithLabels(QWidget):
    def __init__(self, minimum, maximum, value=0, parent=None):
        super(SliderWithLabels, self).__init__(parent)
        self.minimum = minimum
        self.maximum = maximum
        
        # Use a fixed height to ensure consistent layout
        self.setMinimumHeight(80)
        
        # Main layout with no margins for maximum space
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create widget for slider and text box
        controls_widget = QWidget()
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create and setup the slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(minimum)
        self.slider.setMaximum(maximum)
        self.slider.setValue(value)
        
        # Show ticks at key positions
        self.slider.setTickPosition(QSlider.TicksBelow)
        self.slider.setTickInterval((maximum - minimum) // 2)
        
        # Create and setup the value edit box
        self.value_edit = QLineEdit(str(value))
        self.value_edit.setFixedWidth(60)
        self.value_edit.setValidator(QtGui.QIntValidator(minimum, maximum))
        
        # Add both to the controls layout
        controls_layout.addWidget(self.slider)
        controls_layout.addWidget(self.value_edit)
        
        # Create custom widget for labels that draws dynamically
        self.labels_widget = TickLabelsWidget(minimum, maximum)
        self.labels_widget.setFixedHeight(20)
        
        # Add widgets to main layout
        main_layout.addWidget(controls_widget)
        main_layout.addWidget(self.labels_widget)
        main_layout.addSpacing(5)  # Add some extra space at bottom
        
        # Connect signals
        self.slider.valueChanged.connect(self.update_value_edit)
        self.value_edit.editingFinished.connect(self.update_slider)
        
    def update_value_edit(self, value):
        self.value_edit.setText(str(value))
        
    def update_slider(self):
        try:
            value = int(self.value_edit.text())
            value = max(self.slider.minimum(), min(self.slider.maximum(), value))
            self.slider.setValue(value)
        except ValueError:
            self.value_edit.setText(str(self.slider.value()))
            
    def set_range(self, minimum, maximum):
        """Update the range of the slider and labels"""
        self.slider.setMinimum(minimum)
        self.slider.setMaximum(maximum)
        self.value_edit.setValidator(QtGui.QIntValidator(minimum, maximum))
        self.labels_widget.minimum = minimum
        self.labels_widget.maximum = maximum
        self.labels_widget.update()  # Trigger repaint of labels
        
        # Clamp current value if needed
        current = self.slider.value()
        if current < minimum:
            self.slider.setValue(minimum)
        elif current > maximum:
            self.slider.setValue(maximum)
            
    def setValue(self, value):
        self.slider.setValue(value)
        
    def value(self):
        return self.slider.value()


class TickLabelsWidget(QWidget):
    """Custom widget to draw tick labels that align perfectly with slider ticks"""
    def __init__(self, minimum, maximum, parent=None):
        super(TickLabelsWidget, self).__init__(parent)
        self.minimum = minimum
        self.maximum = maximum
        
    def paintEvent(self, event):
        """Override paint event to draw labels at precise positions"""
        painter = QPainter(self)
        painter.setPen(QColor(0, 0, 0))
        
        # Get widget dimensions
        width = self.width()
        height = self.height()
        
        # Calculate positions - 60px offset for value edit box
        usable_width = width - 70  # Account for edit box width + margins
        
        # Draw min label (left)
        min_pos = 10  # Left margin
        painter.drawText(min_pos, 0, 40, height, Qt.AlignLeft | Qt.AlignTop, str(self.minimum))
        
        # Draw zero label (center)
        if self.minimum < 0 and self.maximum > 0:
            # Calculate zero position
            zero_ratio = abs(self.minimum) / (abs(self.minimum) + abs(self.maximum))
            zero_pos = min_pos + zero_ratio * usable_width
            painter.drawText(int(zero_pos-10), 0, 20, height, Qt.AlignHCenter | Qt.AlignTop, "0")
            
        # Draw max label (right)
        max_pos = 10 + usable_width
        painter.drawText(max_pos-40, 0, 40, height, Qt.AlignRight | Qt.AlignTop, str(self.maximum))

class MotorControlUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Motor Control')
        self.max_rpm = 100
        self.rover_ip = "10.30.30.30"
        self.rover_port = 6000
        self.ecu_connector = None
        self.transport = None
        self.connected = False
        self.update_interval = 200  # Default update interval in ms
        
        # Create timer for periodic updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.send_current_speeds)
        
        # Add timer for connection checking
        self.connection_check_timer = QTimer()
        self.connection_check_timer.timeout.connect(self.check_connection_status)
        self.connection_check_timer.setInterval(1000)  # Check every second
        
        self.init_ui()
        ui_logger.info("UI initialized")

    def init_ui(self):
        main_layout = QVBoxLayout()

        # Connection settings
        connection_group = QGroupBox('Connection Settings')
        connection_layout = QFormLayout()
        
        # IP Address input
        self.ip_edit = QLineEdit(self.rover_ip)
        connection_layout.addRow('Rover IP:', self.ip_edit)
        
        # Port input
        self.port_edit = QLineEdit(str(self.rover_port))
        self.port_edit.setValidator(QtGui.QIntValidator(1, 65535))
        connection_layout.addRow('Rover Port:', self.port_edit)
        
        # Update interval input
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(50, 2000)  # 50ms to 2000ms (2 seconds)
        self.interval_spin.setSingleStep(50)
        self.interval_spin.setValue(self.update_interval)
        self.interval_spin.setSuffix(' ms')
        self.interval_spin.setToolTip('Interval between motor speed updates')
        self.interval_spin.valueChanged.connect(self.update_refresh_interval)
        connection_layout.addRow('Update Interval:', self.interval_spin)
        
        # Connect button
        connect_layout = QHBoxLayout()
        self.connect_button = QPushButton('Connect to Rover')
        self.connect_button.clicked.connect(self.toggle_connection)
        connect_layout.addWidget(self.connect_button)
        connection_layout.addRow('', connect_layout)
        
        connection_group.setLayout(connection_layout)
        main_layout.addWidget(connection_group)
        
        # Max RPM input
        form_layout = QFormLayout()
        self.max_rpm_edit = QLineEdit(str(self.max_rpm))
        self.max_rpm_edit.setValidator(QtGui.QIntValidator(1, 10000))
        self.max_rpm_edit.editingFinished.connect(self.update_max_rpm)
        form_layout.addRow('Max motor RPM:', self.max_rpm_edit)
        main_layout.addLayout(form_layout)

        # Stop All Motors button (painted red)
        stop_button = QPushButton('Stop All Motors')
        stop_button.setStyleSheet('background-color: red; color: white; font-weight: bold;')
        stop_button.clicked.connect(self.stop_all_motors)
        main_layout.addWidget(stop_button)

        # Together mode group
        together_group = QGroupBox('Together mode')
        together_layout = QVBoxLayout()
        self.all_same_checkbox = QCheckBox('All motors the same speed')
        self.all_same_checkbox.setChecked(True)
        self.all_same_checkbox.stateChanged.connect(self.toggle_mode)
        together_layout.addWidget(self.all_same_checkbox)
        
        together_layout.addWidget(QLabel('All motors speed'))
        self.all_speed_slider = SliderWithLabels(-self.max_rpm, self.max_rpm, 0)
        self.all_speed_slider.slider.valueChanged.connect(self.set_all_speeds)
        together_layout.addWidget(self.all_speed_slider)
        
        together_group.setLayout(together_layout)
        main_layout.addWidget(together_group)

        # Individual mode
        self.individual_group = QGroupBox('Individual mode')
        individual_layout = QGridLayout()
        self.motor_sliders = []
        
        for i in range(4):
            individual_layout.addWidget(QLabel(f'Motor {i+1} speed'), i, 0)
            slider = SliderWithLabels(-self.max_rpm, self.max_rpm, 0)
            slider.slider.valueChanged.connect(self.individual_slider_changed)
            individual_layout.addWidget(slider, i, 1)
            self.motor_sliders.append(slider)
            
        self.individual_group.setLayout(individual_layout)
        main_layout.addWidget(self.individual_group)

        self.setLayout(main_layout)
        self.toggle_mode()

    def update_max_rpm(self):
        try:
            new_max = int(self.max_rpm_edit.text())
            if new_max < 1:
                new_max = 1
            self.max_rpm = new_max
            
            # Update ranges for all sliders
            self.all_speed_slider.set_range(-self.max_rpm, self.max_rpm)
            for slider in self.motor_sliders:
                slider.set_range(-self.max_rpm, self.max_rpm)
            
            # If connected, update the current motor speeds based on sliders
            if self.connected and self.ecu_connector:
                self.send_current_speeds()
                
        except ValueError:
            self.max_rpm_edit.setText(str(self.max_rpm))

    def toggle_mode(self):
        together = self.all_same_checkbox.isChecked()
        self.individual_group.setDisabled(together)
        if together:
            self.set_all_speeds()
        else:
            # When switching to individual mode, send the current motor speeds
            self.individual_slider_changed()

    def update_refresh_interval(self, value):
        """Update the timer interval for sending speed updates"""
        self.update_interval = value
        ui_logger.debug(f"Update interval changed to {self.update_interval}ms")
        
        # Update the timer if it's running
        if self.connected and self.update_timer.isActive():
            self.update_timer.setInterval(self.update_interval)
            ui_logger.debug(f"Timer interval updated to {self.update_interval}ms")
    
    def toggle_connection(self):
        if self.connected:
            # Disconnect if already connected
            if self.ecu_connector:
                # Stop the timer
                if self.update_timer.isActive():
                    self.update_timer.stop()
                    ui_logger.info("Update timer stopped")
                
                # Stop all motors before disconnecting
                self.stop_all_motors()
                self.ecu_connector.stop()
                self.ecu_connector = None
                self.transport = None
                self.connected = False
                self.connect_button.setText('Connect to Rover')
                ui_logger.info("Disconnected from rover")
                QMessageBox.information(self, 'Disconnected', 'Successfully disconnected from rover.')
                
                # Stop the connection check timer
                self.connection_check_timer.stop()
        else:
            # Get IP and port from the UI
            ip = self.ip_edit.text().strip()
            try:
                port = int(self.port_edit.text().strip())
            except ValueError:
                QMessageBox.warning(self, 'Invalid Port', 'Port must be a valid number between 1-65535.')
                return
            
            # Create transport and ECU connector
            ui_logger.info(f"Attempting to connect to rover at {ip}:{port}")
            self.transport = TCPTransport()
            self.ecu_connector = ECUConnector(self.transport)
            
            # Set up callbacks
            self.ecu_connector.set_callbacks(
                status_callback=lambda msg: ui_logger.info(msg),
                error_callback=lambda msg: ui_logger.error(msg)
            )
            
            # Try to connect
            if self.ecu_connector.connect(ip, port):
                self.connected = True
                self.connect_button.setText('Disconnect')
                ui_logger.info(f"Connected to rover at {ip}:{port}")
                
                # Start the ECUConnector worker thread
                self.ecu_connector.start()
                
                # Start timers
                self.update_timer.setInterval(self.update_interval)
                self.update_timer.start()
                self.connection_check_timer.start()
                
                # Send the initial speeds
                success = self.send_current_speeds()
                ui_logger.info(f"Initial speed update sent: {'Success' if success else 'Failed'}")
                
                QMessageBox.information(self, 'Connected', 
                                      f'Successfully connected to rover at {ip}:{port}\n'
                                      f'Speed updates every {self.update_interval}ms')
            else:
                ui_logger.error(f"Failed to connect to rover at {ip}:{port}")
                QMessageBox.warning(self, 'Connection Failed', f'Failed to connect to rover at {ip}:{port}')
                self.ecu_connector = None
                self.transport = None

    def check_connection_status(self):
        """Periodic check of connection status"""
        if self.ecu_connector and not self.ecu_connector.is_connected():
            ui_logger.warning("Connection lost detected during status check")
            self.handle_connection_lost()

    def handle_connection_lost(self):
        """Handle lost connection"""
        self.update_timer.stop()
        self.connection_check_timer.stop()
        self.connected = False
        self.connect_button.setText('Connect to Rover')
        
        # Show warning to user
        QMessageBox.warning(self, 'Connection Lost', 
                          'Connection to rover was lost. Please reconnect.')

    def send_current_speeds(self):
        """Send speed updates to rover"""
        if not self.ecu_connector or not self.ecu_connector.is_connected():
            ui_logger.error("Cannot send speeds - not connected")
            self.handle_connection_lost()
            return False
            
        try:
            if self.all_same_checkbox.isChecked():
                value = self.all_speed_slider.value()
                speeds = [value] * 4
            else:
                speeds = [slider.value() for slider in self.motor_sliders]
            
            ui_logger.debug(f"Sending speeds: {speeds}")
            self.ecu_connector.set_all_motors_speed(speeds)
            return True
            
        except Exception as e:
            ui_logger.exception(f"Error sending speeds: {str(e)}")
            self.handle_connection_lost()
            return False

    def set_all_speeds(self):
        """Set all motor sliders to the same value and send to rover"""
        value = self.all_speed_slider.value()
        for slider in self.motor_sliders:
            slider.setValue(value)
        
        # Send speed command to rover if connected
        if self.connected and self.ecu_connector:
            ui_logger.debug(f"Setting all speeds to {value} RPM")
            self.ecu_connector.set_all_motors_speed([value] * 4)

    def individual_slider_changed(self):
        if not self.all_same_checkbox.isChecked():
            speeds = [slider.value() for slider in self.motor_sliders]
            
            # Send speeds to rover if connected
            if self.connected and self.ecu_connector:
                ui_logger.debug(f"Setting individual speeds to {speeds} RPM")
                self.ecu_connector.set_all_motors_speed(speeds)

    def stop_all_motors(self):
        # Set all UI sliders to zero
        ui_logger.info("Stop all motors requested")
        self.all_speed_slider.setValue(0)
        for slider in self.motor_sliders:
            slider.setValue(0)
        
        # Send stop command to rover if connected
        if self.connected and self.ecu_connector:
            try:
                ui_logger.info("Sending stop command to rover")
                # Stop all motors
                self.ecu_connector.set_all_motors_speed([0] * 4)
                
            except Exception as e:
                ui_logger.exception(f"Error stopping motors: {str(e)}")
                QMessageBox.warning(self, 'Error Stopping Motors', 
                                  f'Failed to stop motors: {str(e)}\n'
                                  'Please check connection and try again.')

    def change_log_level(self, level: str) -> None:
        """Change log level for both loggers"""
        numeric_level = getattr(logging, level)
        ui_logger.setLevel(numeric_level)
        ecu_logger.setLevel(numeric_level)
        ui_logger.info(f"Log level changed to {level}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Set application style for better appearance
    app.setStyle('Fusion')
    
    window = MotorControlUI()
    window.show()
    
    # Make sure to stop motors on exit
    try:
        sys.exit(app.exec_())
    except SystemExit:
        # Attempt to stop motors if the UI is closing
        if window.connected and window.ecu_connector:
            window.stop_all_motors()
            window.ecu_connector.disconnect()
    app.setStyle('Fusion')
    
    window = MotorControlUI()
    window.show()
    
    # Make sure to stop motors on exit
    try:
        sys.exit(app.exec_())
    except SystemExit:
        # Attempt to stop motors if the UI is closing
        if window.connected and window.rover:
            window.stop_all_motors()
            window.rover.disconnect()
                                  

    def change_log_level(self, level: str) -> None:
        """Change log level for both loggers"""
        numeric_level = getattr(logging, level)
        ui_logger.setLevel(numeric_level)
        ecu_logger.setLevel(numeric_level)
        ui_logger.info(f"Log level changed to {level}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Set application style for better appearance
    app.setStyle('Fusion')
    
    window = MotorControlUI()
    window.show()
    
    # Make sure to stop motors on exit
    try:
        sys.exit(app.exec_())
    except SystemExit:
        # Attempt to stop motors if the UI is closing
        if window.connected and window.ecu_connector:
            window.stop_all_motors()
            window.ecu_connector.disconnect()
    app = QApplication(sys.argv)
    
    # Set application style for better appearance
    app.setStyle('Fusion')
    
    window = MotorControlUI()
    window.show()
    
    # Make sure to stop motors on exit
    try:
        sys.exit(app.exec_())
    except SystemExit:
        # Attempt to stop motors if the UI is closing
        if window.connected and window.rover:
            window.stop_all_motors()
            window.rover.disconnect()
