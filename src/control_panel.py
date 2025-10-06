from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, 
                              QCheckBox, QSlider, QLabel, QLineEdit, QPushButton,
                              QSpinBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QBrush


class MotorSlider(QWidget):
    """Custom slider widget with value display and edit capability."""
    valueChanged = pyqtSignal(int)
    
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.label_text = label
        self.setup_ui()
        
    def setup_ui(self):
        layout = QHBoxLayout(self)
        
        # Label
        label = QLabel(self.label_text)
        label.setMinimumWidth(60)
        layout.addWidget(label)
        
        # Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(-100)
        self.slider.setMaximum(100)
        self.slider.setValue(0)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setTickInterval(50)
        self.slider.valueChanged.connect(self.on_slider_changed)
        layout.addWidget(self.slider, stretch=1)
        
        # Value display/edit
        self.value_edit = QSpinBox()
        self.value_edit.setMinimum(-100)
        self.value_edit.setMaximum(100)
        self.value_edit.setValue(0)
        self.value_edit.setMinimumWidth(60)
        self.value_edit.valueChanged.connect(self.on_edit_changed)
        layout.addWidget(self.value_edit)
        
    def on_slider_changed(self, value):
        self.value_edit.blockSignals(True)
        self.value_edit.setValue(value)
        self.value_edit.blockSignals(False)
        self.valueChanged.emit(value)
        
    def on_edit_changed(self, value):
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self.valueChanged.emit(value)
        
    def set_range(self, min_val, max_val):
        """Update slider and spinbox range."""
        self.slider.setMinimum(min_val)
        self.slider.setMaximum(max_val)
        self.value_edit.setMinimum(min_val)
        self.value_edit.setMaximum(max_val)
        
    def value(self):
        return self.slider.value()
        
    def setValue(self, value):
        self.slider.setValue(value)


class JoystickWidget(QWidget):
    """Virtual joystick widget for robot control."""
    positionChanged = pyqtSignal(float, float)  # x, y in range [-1, 1]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(120, 120)
        self.setMaximumSize(150, 150)
        self.position_x = 0.0
        self.position_y = 0.0
        self.is_pressed = False
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw outer circle (boundary)
        center_x = self.width() // 2
        center_y = self.height() // 2
        radius = min(center_x, center_y) - 10
        
        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        painter.setBrush(QBrush(Qt.GlobalColor.lightGray))
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
        
        # Draw center cross
        painter.setPen(QPen(Qt.GlobalColor.gray, 1))
        painter.drawLine(center_x - 10, center_y, center_x + 10, center_y)
        painter.drawLine(center_x, center_y - 10, center_x, center_y + 10)
        
        # Draw joystick position
        joy_x = int(center_x + self.position_x * radius)
        joy_y = int(center_y - self.position_y * radius)  # Invert Y for screen coordinates
        
        painter.setPen(QPen(Qt.GlobalColor.darkBlue, 2))
        painter.setBrush(QBrush(Qt.GlobalColor.blue))
        painter.drawEllipse(joy_x - 10, joy_y - 10, 20, 20)
        
    def mousePressEvent(self, event):
        self.is_pressed = True
        self.updatePosition(event.pos())
        
    def mouseMoveEvent(self, event):
        if self.is_pressed:
            self.updatePosition(event.pos())
            
    def mouseReleaseEvent(self, event):
        self.is_pressed = False
        self.position_x = 0.0
        self.position_y = 0.0
        self.update()
        self.positionChanged.emit(self.position_x, self.position_y)
        
    def updatePosition(self, pos):
        center_x = self.width() // 2
        center_y = self.height() // 2
        radius = min(center_x, center_y) - 10
        
        # Calculate position relative to center
        dx = pos.x() - center_x
        dy = center_y - pos.y()  # Invert Y for screen coordinates
        
        # Normalize to [-1, 1]
        distance = (dx**2 + dy**2)**0.5
        if distance > radius:
            dx = dx * radius / distance
            dy = dy * radius / distance
            
        self.position_x = dx / radius
        self.position_y = dy / radius
        
        self.update()
        self.positionChanged.emit(self.position_x, self.position_y)


class ControlPanel(QWidget):
    """Control panel with three sections: connection, sliders, and gamepad."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.motor_sliders = []
        self.ecu_connector = None
        self.setup_ui()
        
    def set_ecu_connector(self, ecu_connector):
        """Set the ECU connector adapter instance."""
        self.ecu_connector = ecu_connector
        
    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Section 1: Connection Settings
        connection_section = self.create_connection_section()
        main_layout.addWidget(connection_section, stretch=1)
        
        # Section 2: Sliders (Motor Control)
        sliders_section = self.create_sliders_section()
        main_layout.addWidget(sliders_section, stretch=3)
        
        # Section 3: Gamepad/Joystick
        gamepad_section = self.create_gamepad_section()
        main_layout.addWidget(gamepad_section, stretch=1)
        
        # Initialize state
        self.on_max_rpm_changed(100)
        
    def create_connection_section(self):
        """Create connection settings section."""
        group = QGroupBox("Connection")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)
        
        # Rover IP
        self.ip_edit = QLineEdit("10.30.30.30")
        layout.addWidget(QLabel("Rover IP:"))
        layout.addWidget(self.ip_edit)
        
        # Port
        self.port_spinbox = QSpinBox()
        self.port_spinbox.setMinimum(1)
        self.port_spinbox.setMaximum(65535)
        self.port_spinbox.setValue(6000)
        layout.addWidget(QLabel("Port:"))
        layout.addWidget(self.port_spinbox)
        
        # Connect button
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.on_connect_clicked)
        layout.addWidget(self.connect_button)
        
        # Max RPM
        self.max_rpm_spinbox = QSpinBox()
        self.max_rpm_spinbox.setMinimum(1)
        self.max_rpm_spinbox.setMaximum(10000)
        self.max_rpm_spinbox.setValue(100)
        self.max_rpm_spinbox.valueChanged.connect(self.on_max_rpm_changed)
        layout.addWidget(QLabel("Max RPM:"))
        layout.addWidget(self.max_rpm_spinbox)
        
        # Refresh interval
        self.refresh_spinbox = QSpinBox()
        self.refresh_spinbox.setMinimum(50)
        self.refresh_spinbox.setMaximum(5000)
        self.refresh_spinbox.setValue(200)
        self.refresh_spinbox.valueChanged.connect(self.on_refresh_interval_changed)
        layout.addWidget(QLabel("Refresh (ms):"))
        layout.addWidget(self.refresh_spinbox)
        
        layout.addStretch()
        return group
        
    def on_refresh_interval_changed(self, value):
        """Handle refresh interval change."""
        if self.ecu_connector:
            self.ecu_connector.set_refresh_interval(value)
            
    def create_sliders_section(self):
        """Create sliders section for motor control."""
        group = QGroupBox("Motor Control")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)
        
        # Together mode group
        together_group = QGroupBox("Together Mode")
        together_layout = QVBoxLayout(together_group)
        together_layout.setContentsMargins(5, 5, 5, 5)
        together_layout.setSpacing(2)
        
        self.all_same_checkbox = QCheckBox("All motors the same speed")
        self.all_same_checkbox.stateChanged.connect(self.on_mode_changed)
        together_layout.addWidget(self.all_same_checkbox)
        
        self.all_motors_slider = MotorSlider("All:")
        self.all_motors_slider.valueChanged.connect(self.on_all_motors_changed)
        together_layout.addWidget(self.all_motors_slider)
        
        layout.addWidget(together_group)
        
        # Individual mode group
        individual_group = QGroupBox("Individual Mode")
        individual_layout = QVBoxLayout(individual_group)
        individual_layout.setContentsMargins(5, 5, 5, 5)
        individual_layout.setSpacing(2)
        
        self.motor_sliders = []
        for i in range(4):
            slider = MotorSlider(f"M{i+1}:")
            slider.valueChanged.connect(self.on_individual_motor_changed)
            individual_layout.addWidget(slider)
            self.motor_sliders.append(slider)
        
        self.individual_group = individual_group
        layout.addWidget(individual_group)
        
        # Stop button
        self.stop_button = QPushButton("STOP ALL")
        self.stop_button.setStyleSheet("QPushButton { background-color: red; color: white; font-weight: bold; padding: 5px; }")
        self.stop_button.setMaximumHeight(30)
        self.stop_button.clicked.connect(self.on_stop_clicked)
        layout.addWidget(self.stop_button)
        
        return group
        
    def create_gamepad_section(self):
        """Create gamepad/joystick section."""
        group = QGroupBox("Joystick Control")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)
        
        # Virtual joystick
        self.joystick = JoystickWidget()
        self.joystick.positionChanged.connect(self.on_joystick_changed)
        layout.addWidget(self.joystick, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Position display
        self.position_label = QLabel("X: 0.00, Y: 0.00")
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.position_label)
        
        # Gamepad status
        self.gamepad_status = QLabel("No gamepad")
        self.gamepad_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.gamepad_status)
        
        layout.addStretch()
        return group
        
    def on_mode_changed(self, state):
        """Handle mode change between together and individual."""
        is_together = state == Qt.CheckState.Checked.value
        self.individual_group.setEnabled(not is_together)
        
        if is_together:
            # Sync all motor sliders to the all_motors value
            value = self.all_motors_slider.value()
            for slider in self.motor_sliders:
                slider.setValue(value)
                
    def on_connect_clicked(self):
        """Handle connect/disconnect button."""
        if not self.ecu_connector:
            return
            
        if self.connect_button.text() == "Connect":
            ip = self.ip_edit.text()
            port = self.port_spinbox.value()
            success = self.ecu_connector.connect_to_rover(ip, port)
            if success:
                self.connect_button.setText("Disconnect")
        else:
            self.ecu_connector.disconnect_from_rover()
            self.connect_button.setText("Connect")
            
    def on_connection_state_changed(self, connected: bool):
        """Handle connection state changes from ECU connector."""
        if connected:
            self.connect_button.setText("Disconnect")
        else:
            self.connect_button.setText("Connect")
            
    def on_error_occurred(self, error_message: str):
        """Handle errors from ECU connector."""
        # TODO: Display error in UI (status bar, message box, etc.)
        print(f"ECU Error: {error_message}")
        
    def on_all_motors_changed(self, value):
        """Handle all motors slider change."""
        if self.all_same_checkbox.isChecked():
            for slider in self.motor_sliders:
                slider.setValue(value)
            # Send to ECU connector
            if self.ecu_connector:
                speeds = [value] * 4
                self.ecu_connector.set_all_motors_speed(speeds)
                
    def on_individual_motor_changed(self):
        """Handle individual motor slider changes."""
        if not self.all_same_checkbox.isChecked() and self.ecu_connector:
            speeds = [slider.value() for slider in self.motor_sliders]
            self.ecu_connector.set_all_motors_speed(speeds)
            
    def on_max_rpm_changed(self, value):
        """Update all slider ranges when max RPM changes."""
        self.all_motors_slider.set_range(-value, value)
        for slider in self.motor_sliders:
            slider.set_range(-value, value)
            
    def on_stop_clicked(self):
        """Stop all motors by setting speeds to zero."""
        self.all_motors_slider.setValue(0)
        for slider in self.motor_sliders:
            slider.setValue(0)
        # Send stop command to ECU
        if self.ecu_connector:
            self.ecu_connector.set_all_motors_speed([0, 0, 0, 0])
            
    def on_joystick_changed(self, x, y):
        """Handle joystick position changes."""
        self.position_label.setText(f"X: {x:.2f}, Y: {y:.2f}")
        
        # Convert joystick position to differential drive
        if self.ecu_connector and self.ecu_connector.is_connected():
            max_rpm = self.max_rpm_spinbox.value()
            
            # Differential drive calculation
            forward = y * max_rpm
            turn = x * max_rpm
            
            left_speed = int(forward - turn)
            right_speed = int(forward + turn)
            
            # For 4-motor setup, assume left side = motors 0,2 and right side = motors 1,3
            speeds = [left_speed, right_speed, left_speed, right_speed]
            
            # Clamp to max RPM range
            speeds = [max(-max_rpm, min(max_rpm, speed)) for speed in speeds]
            
            self.ecu_connector.set_all_motors_speed(speeds)
