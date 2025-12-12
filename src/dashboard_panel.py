from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QHBoxLayout, QGroupBox, QCheckBox, QLabel, QSpinBox, QSplitter, QFileDialog, QPushButton, QProgressBar, QComboBox
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QDateTimeAxis
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QDateTime, QRectF, QPointF
from PyQt6.QtGui import QPen, QColor, QPainter, QBrush, QPolygonF
import pyqtgraph as pg  # For better chart performance
import numpy as np
import re
import logging
import math


class PIDRegulatorTab(QWidget):
    """PID Regulator tab with motor speed charts."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.encoder_ticks_per_rev = 1328  # Single value for all motors
        self.setpoint_data = [[], [], [], []]  # Setpoint history for each motor
        self.current_data = [[], [], [], []]  # Encoder value history for each motor (in RPM)
        self.time_data = [[], [], [], []]  # Time stamps in milliseconds
        self.max_points = 1000  # Maximum points to keep in chart
        self.ecu_connector_adapter = None
        self.start_time_ms = None  # Track start time for relative timestamps
        self.cumulative_time_ms = 0  # Cumulative time in milliseconds
        self.initialized = False  # Track if we've received first data
        self.autoscroll_window_ms = 10000  # Show last 10 seconds by default
        self.setup_ui()
        
        # Initialize chart with zero values at time 0
        for i in range(4):
            self.setpoint_data[i].append(0)
            self.current_data[i].append(0)
            self.time_data[i].append(0)
            self.setpoint_curves[i].setData([0], [0])
            self.current_curves[i].setData([0], [0])
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Controls section
        controls_group = QGroupBox("Chart Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        # Motor selection checkboxes
        self.motor_checkboxes = []
        for i in range(4):
            checkbox = QCheckBox(f"Motor {i+1}")
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self.on_motor_selection_changed)
            controls_layout.addWidget(checkbox)
            self.motor_checkboxes.append(checkbox)
        
        controls_layout.addStretch()
        
        # Autoscroll checkbox
        self.autoscroll_checkbox = QCheckBox("Auto-scroll")
        self.autoscroll_checkbox.setChecked(True)
        self.autoscroll_checkbox.stateChanged.connect(self.on_autoscroll_changed)
        controls_layout.addWidget(self.autoscroll_checkbox)
        
        # Encoder ticks configuration (single value for all motors)
        ticks_label = QLabel("Encoder Ticks/Rev:")
        self.ticks_spinbox = QSpinBox()
        self.ticks_spinbox.setMinimum(1)
        self.ticks_spinbox.setMaximum(10000)
        self.ticks_spinbox.setValue(1328)
        self.ticks_spinbox.setToolTip("Encoder ticks per revolution (applies to all motors)")
        self.ticks_spinbox.valueChanged.connect(self.on_ticks_changed)
        controls_layout.addWidget(ticks_label)
        controls_layout.addWidget(self.ticks_spinbox)
        
        layout.addWidget(controls_group)
        
        # Chart section
        self.setup_chart()
        layout.addWidget(self.chart_widget)

    def set_ecu_connector(self, ecu_connector_adapter):
        """Attach the ECU connector adapter to this tab.

        The adapter is used to update encoder-ticks configuration when the
        user changes the ticks spinboxes so RPM calculations elsewhere use the
        same configuration.
        """
        self.ecu_connector_adapter = ecu_connector_adapter
        
    def setup_chart(self):
        """Setup the chart using pyqtgraph for better performance."""
        self.chart_widget = pg.PlotWidget()
        self.chart_widget.setBackground('w')
        self.chart_widget.setTitle("Motor Speed Control - Setpoint vs Actual RPM")
        self.chart_widget.setLabel('left', 'RPM')
        self.chart_widget.setLabel('bottom', 'Time (ms)')
        
        # Create plot items for each motor
        self.setpoint_curves = []
        self.current_curves = []
        colors = ['red', 'blue', 'green', 'orange']
        
        for i in range(4):
            # Setpoint curve (dotted)
            setpoint_curve = self.chart_widget.plot(pen=pg.mkPen(color=colors[i], style=Qt.PenStyle.DotLine, width=2), name=f'Motor {i+1} Setpoint')
            self.setpoint_curves.append(setpoint_curve)
            
            # Actual RPM curve (solid)
            current_curve = self.chart_widget.plot(pen=pg.mkPen(color=colors[i], width=2), name=f'Motor {i+1} RPM')
            self.current_curves.append(current_curve)
        
        # Legend
        self.chart_widget.addLegend()
        
        # Enable scroll and zoom only for X axis
        self.chart_widget.setMouseEnabled(x=True, y=False)
        
        # Set initial axis ranges starting from 0
        self.max_rpm = 100  # Default max RPM
        self.chart_widget.setXRange(0, 1000, padding=0)  # 0 to 1000ms initially
        self.chart_widget.setYRange(-self.max_rpm, self.max_rpm, padding=0)
        
        # Disable auto-range initially, will adjust as data comes in
        self.chart_widget.disableAutoRange()
        
    def on_motor_selection_changed(self):
        """Update chart visibility based on motor selection."""
        for i, checkbox in enumerate(self.motor_checkboxes):
            visible = checkbox.isChecked()
            self.setpoint_curves[i].setVisible(visible)
            self.current_curves[i].setVisible(visible)
    
    def on_autoscroll_changed(self):
        """Handle autoscroll checkbox state change."""
        is_autoscroll = self.autoscroll_checkbox.isChecked()
        if not is_autoscroll:
            # Re-enable auto-range when autoscroll is disabled to allow zoom
            self.chart_widget.enableAutoRange(axis='x', enable=False)
            self.chart_widget.setMouseEnabled(x=True, y=False)
        else:
            # When autoscroll is enabled, disable manual control
            self.chart_widget.disableAutoRange(axis='x')
            
    def on_ticks_changed(self, value):
        """Update encoder ticks per revolution for all motors."""
        self.encoder_ticks_per_rev = value
        # Notify ECU connector adapter so it uses the same value
        if self.ecu_connector_adapter and hasattr(self.ecu_connector_adapter, 'set_encoder_ticks_per_rev'):
            try:
                # Set the same value for all 4 motors
                for motor_id in range(4):
                    self.ecu_connector_adapter.set_encoder_ticks_per_rev(motor_id, value)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to update encoder ticks in adapter: {e}")
    
    def update_y_axis_range(self, max_rpm: int):
        """Update the Y-axis range of the chart based on max RPM value."""
        self.max_rpm = max_rpm
        self.chart_widget.setYRange(-max_rpm, max_rpm, padding=0)
        
    def update_data(self, setpoints, encoder_values, time_elapsed_seconds):
        """Update chart data with new setpoints and encoder values.
        
        Args:
            setpoints: List of 4 setpoint values (RPM from sliders)
            encoder_values: List of 4 encoder delta values from ECU (ticks since last read)
            time_elapsed_seconds: Time interval since last update in seconds
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"PIDRegulatorTab.update_data called: setpoints={setpoints}, encoder_deltas={encoder_values}, time_elapsed={time_elapsed_seconds}s")
        
        # Convert time_elapsed to milliseconds and accumulate
        time_elapsed_ms = time_elapsed_seconds * 1000
        self.cumulative_time_ms += time_elapsed_ms
        
        logger.info(f"Cumulative time: {self.cumulative_time_ms}ms")
        
        for i in range(4):
            # encoder_values already contains delta (ticks since last read)
            encoder_delta = encoder_values[i]
            
            # Calculate RPM: (delta_ticks / ticks_per_rev) * (60 / time_in_seconds)
            if time_elapsed_seconds > 0 and self.encoder_ticks_per_rev > 0:
                rpm = (encoder_delta / self.encoder_ticks_per_rev) * (60.0 / time_elapsed_seconds)
            else:
                rpm = 0.0
            
            logger.debug(f"Motor {i}: encoder_delta={encoder_delta}, rpm={rpm:.2f}")
            
            # Add new data points
            self.setpoint_data[i].append(setpoints[i])
            self.current_data[i].append(rpm)  # Store calculated RPM
            self.time_data[i].append(self.cumulative_time_ms)
            
            # Limit data points
            if len(self.setpoint_data[i]) > self.max_points:
                self.setpoint_data[i].pop(0)
                self.current_data[i].pop(0)
                self.time_data[i].pop(0)
            
            # Update curves
            self.setpoint_curves[i].setData(self.time_data[i], self.setpoint_data[i])
            self.current_curves[i].setData(self.time_data[i], self.current_data[i])
        
        # Autoscroll: adjust X-axis to show the most recent data
        if self.autoscroll_checkbox.isChecked():
            if self.cumulative_time_ms > self.autoscroll_window_ms:
                # Show the last window of data
                x_min = self.cumulative_time_ms - self.autoscroll_window_ms
                x_max = self.cumulative_time_ms
            else:
                # Show all data from 0 if we haven't filled the window yet
                x_min = 0
                x_max = max(self.autoscroll_window_ms, self.cumulative_time_ms)
            
            self.chart_widget.setXRange(x_min, x_max, padding=0)
        
        logger.info(f"Chart updated. Motor 0 has {len(self.time_data[0])} data points")
            
    def calculate_rpm(self, encoder_delta, time_interval_seconds):
        """Calculate RPM from encoder delta and time interval.
        
        Args:
            encoder_delta: Change in encoder ticks since last reading
            time_interval_seconds: Time elapsed since last reading in seconds
            
        Returns:
            RPM value
        """
        if time_interval_seconds <= 0 or self.encoder_ticks_per_rev <= 0:
            return 0.0
        
        # RPM = (delta_ticks / ticks_per_rev) * (60 / time_in_seconds)
        rpm = (encoder_delta / self.encoder_ticks_per_rev) * (60.0 / time_interval_seconds)
        return rpm
        
    def clear_data(self):
        """Clear all chart data."""
        self.cumulative_time_ms = 0
        for i in range(4):
            self.setpoint_data[i].clear()
            self.current_data[i].clear()
            self.time_data[i].clear()
            self.setpoint_curves[i].setData([], [])
            self.current_curves[i].setData([], [])


class LogPIDTab(QWidget):
    """PID Log Analysis tab with charts from log file data."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.log_data = {
            'timestamp': [],  # Relative time in seconds
            'motor': [],      # Motor ID (1-4)
            'setpoint': [],   # Set point values
            'current': [],    # Current values
            'error': [],      # Error values
            'pid_output': [], # PID output values
            'pwm': []         # PWM values
        }
        self.max_points = 5000  # Maximum points to keep in chart
        self.autoscroll_window_ms = 10000  # Show last 10 seconds by default
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # File selection controls
        file_group = QGroupBox("Log File")
        file_layout = QHBoxLayout(file_group)
        
        self.file_path_label = QLabel("No file selected")
        self.select_file_button = QPushButton("Select Log File")
        self.select_file_button.clicked.connect(self.select_log_file)
        
        file_layout.addWidget(self.file_path_label)
        file_layout.addWidget(self.select_file_button)
        
        layout.addWidget(file_group)
        
        # Progress bar for parsing
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Chart controls
        controls_group = QGroupBox("Chart Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        # Motor selection checkboxes
        self.motor_checkboxes = []
        for i in range(4):
            checkbox = QCheckBox(f"Motor {i+1}")
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self.on_motor_selection_changed)
            controls_layout.addWidget(checkbox)
            self.motor_checkboxes.append(checkbox)
        
        controls_layout.addStretch()
        
        # Autoscroll checkbox
        self.autoscroll_checkbox = QCheckBox("Auto-scroll")
        self.autoscroll_checkbox.setChecked(True)
        self.autoscroll_checkbox.stateChanged.connect(self.on_autoscroll_changed)
        controls_layout.addWidget(self.autoscroll_checkbox)
        
        layout.addWidget(controls_group)
        
        # Chart section
        self.setup_chart()
        layout.addWidget(self.chart_widget)
        
    def setup_chart(self):
        """Setup the chart using pyqtgraph for better performance."""
        self.chart_widget = pg.PlotWidget()
        self.chart_widget.setBackground('w')
        self.chart_widget.setTitle("PID Log Analysis - Set Point vs Current Value & PWM")
        self.chart_widget.setLabel('left', 'Value')
        self.chart_widget.setLabel('bottom', 'Time (s)')
        
        # Create plot items for each motor - setpoint, current, and PWM
        self.setpoint_curves = []
        self.current_curves = []
        self.pwm_curves = []
        colors = ['red', 'blue', 'green', 'orange']
        
        for i in range(4):
            # Setpoint curve (dotted)
            setpoint_curve = self.chart_widget.plot(pen=pg.mkPen(color=colors[i], style=Qt.PenStyle.DotLine, width=2), name=f'Motor {i+1} Setpoint')
            self.setpoint_curves.append(setpoint_curve)
            
            # Current value curve (solid)
            current_curve = self.chart_widget.plot(pen=pg.mkPen(color=colors[i], width=2), name=f'Motor {i+1} Current')
            self.current_curves.append(current_curve)
            
            # PWM curve (dashed)
            pwm_curve = self.chart_widget.plot(pen=pg.mkPen(color=colors[i], style=Qt.PenStyle.DashLine, width=2), name=f'Motor {i+1} PWM')
            self.pwm_curves.append(pwm_curve)
        
        # Legend
        self.chart_widget.addLegend()
        
        # Enable scroll and zoom only for X axis
        self.chart_widget.setMouseEnabled(x=True, y=False)
        
        # Set initial axis ranges
        self.chart_widget.setXRange(0, 10, padding=0)  # 0 to 10 seconds initially
        self.chart_widget.setYRange(-100, 100, padding=0)  # Default range
        
        # Disable auto-range initially
        self.chart_widget.disableAutoRange()
        
    def select_log_file(self):
        """Open file dialog to select log file and parse it automatically."""
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        file_dialog.setNameFilter("Log files (*.log *.txt);;All files (*)")
        
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.log_file_path = selected_files[0]
                self.file_path_label.setText(f"Selected: {self.log_file_path.split('/')[-1]}")
                # Parse automatically when file is selected
                self.parse_log_file()
                
    def parse_log_file(self):
        """Parse the selected log file for PID DUMP lines."""
        if not hasattr(self, 'log_file_path'):
            return
            
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        try:
            # Clear existing data
            self.clear_data()
            
            # Parse log file
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            self.progress_bar.setRange(0, len(lines))
            
            # Regex pattern to match PID DUMP lines
            pattern = r'I(\d{4})\s+(\d{2}:\d{2}:\d{2}\.\d{6})\s+\d+\s+.*?\] \[INFO\] PID DUMP Motor: (\d+) Set point: ([-\d]+) Current value: ([-\d]+) Error: ([-\d]+) PID output: ([-\d]+) PWM: ([-\d]+)'
            
            start_time = None
            
            for i, line in enumerate(lines):
                self.progress_bar.setValue(i + 1)
                
                match = re.search(pattern, line)
                if match:
                    # Extract timestamp
                    date_str, time_str = match.group(1), match.group(2)
                    # Convert to seconds since start
                    time_parts = time_str.split(':')
                    hours = int(time_parts[0])
                    minutes = int(time_parts[1])
                    seconds = float(time_parts[2])
                    total_seconds = hours * 3600 + minutes * 60 + seconds
                    
                    if start_time is None:
                        start_time = total_seconds
                    
                    relative_time = total_seconds - start_time
                    
                    # Extract data
                    motor_id = int(match.group(3))
                    setpoint = int(match.group(4)) / 100.0  # Divide by 100 for actual value
                    current = int(match.group(5)) / 100.0   # Divide by 100 for actual value
                    error = int(match.group(6))
                    pid_output = int(match.group(7))
                    pwm = int(match.group(8))
                    
                    # Store data
                    self.log_data['timestamp'].append(relative_time)
                    self.log_data['motor'].append(motor_id)
                    self.log_data['setpoint'].append(setpoint)
                    self.log_data['current'].append(current)
                    self.log_data['error'].append(error)
                    self.log_data['pid_output'].append(pid_output)
                    self.log_data['pwm'].append(pwm)
            
            # Update chart with parsed data
            self.update_chart()
            
            logging.getLogger(__name__).info(f"Parsed {len(self.log_data['timestamp'])} PID DUMP entries from log file")
            
        except Exception as e:
            logging.getLogger(__name__).error(f"Error parsing log file: {str(e)}")
        finally:
            self.progress_bar.setVisible(False)
            
    def update_chart(self):
        """Update chart with parsed log data."""
        if not self.log_data['timestamp']:
            return
            
        # Group data by motor
        motor_data = {1: {'time': [], 'setpoint': [], 'current': [], 'error': [], 'pid_output': [], 'pwm': []},
                     2: {'time': [], 'setpoint': [], 'current': [], 'error': [], 'pid_output': [], 'pwm': []},
                     3: {'time': [], 'setpoint': [], 'current': [], 'error': [], 'pid_output': [], 'pwm': []},
                     4: {'time': [], 'setpoint': [], 'current': [], 'error': [], 'pid_output': [], 'pwm': []}}
        
        for i in range(len(self.log_data['timestamp'])):
            motor_id = self.log_data['motor'][i]
            if motor_id in motor_data:
                motor_data[motor_id]['time'].append(self.log_data['timestamp'][i])
                motor_data[motor_id]['setpoint'].append(self.log_data['setpoint'][i])
                motor_data[motor_id]['current'].append(self.log_data['current'][i])
                motor_data[motor_id]['error'].append(self.log_data['error'][i])
                motor_data[motor_id]['pid_output'].append(self.log_data['pid_output'][i])
                motor_data[motor_id]['pwm'].append(self.log_data['pwm'][i])
        
        # Update curves - always show setpoint, current, and PWM
        for motor_id in range(1, 5):
            motor_idx = motor_id - 1
            data = motor_data[motor_id]
            
            if data['time']:
                # Setpoint curve (dotted)
                self.setpoint_curves[motor_idx].setData(data['time'], data['setpoint'])
                
                # Current value curve (solid)
                self.current_curves[motor_idx].setData(data['time'], data['current'])
                
                # PWM curve (dashed)
                self.pwm_curves[motor_idx].setData(data['time'], data['pwm'])
        
        # Update axis ranges
        if self.log_data['timestamp']:
            max_time = max(self.log_data['timestamp'])
            
            # Autoscroll: adjust X-axis to show the most recent data
            if self.autoscroll_checkbox.isChecked():
                if max_time * 1000 > self.autoscroll_window_ms:  # Convert to ms for comparison
                    # Show the last window of data
                    x_min = max_time - (self.autoscroll_window_ms / 1000)  # Convert back to seconds
                    x_max = max_time
                else:
                    # Show all data from 0 if we haven't filled the window yet
                    x_min = 0
                    x_max = max(self.autoscroll_window_ms / 1000, max_time)  # Convert back to seconds
                
                self.chart_widget.setXRange(x_min, x_max, padding=0)
            else:
                # When autoscroll is disabled, show all data
                self.chart_widget.setXRange(0, max_time, padding=0.05)
            
            # Auto-scale Y axis based on visible data
            all_values = []
            for motor_id in motor_data.values():
                if motor_data[motor_id]['time']:  # Only include motors with data
                    all_values.extend(motor_data[motor_id]['setpoint'])
                    all_values.extend(motor_data[motor_id]['current'])
                    all_values.extend(motor_data[motor_id]['pwm'])
            
            if all_values:
                y_min, y_max = min(all_values), max(all_values)
                # Set Y-axis range to min value to max value + 50
                self.chart_widget.setYRange(y_min, y_max + 50, padding=0)
        
    def on_motor_selection_changed(self):
        """Update chart visibility based on motor selection."""
        for i, checkbox in enumerate(self.motor_checkboxes):
            visible = checkbox.isChecked()
            self.setpoint_curves[i].setVisible(visible)
            self.current_curves[i].setVisible(visible)
            self.pwm_curves[i].setVisible(visible)
            
    def on_autoscroll_changed(self):
        """Handle autoscroll checkbox state change."""
        is_autoscroll = self.autoscroll_checkbox.isChecked()
        if not is_autoscroll:
            # Re-enable auto-range when autoscroll is disabled to allow zoom
            self.chart_widget.enableAutoRange(axis='x', enable=False)
            self.chart_widget.setMouseEnabled(x=True, y=False)
        else:
            # When autoscroll is enabled, disable manual control
            self.chart_widget.disableAutoRange(axis='x')
            # Update chart to apply autoscroll immediately
            self.update_chart()
        
    def clear_data(self):
        """Clear all parsed data."""
        self.log_data = {
            'timestamp': [],
            'motor': [],
            'setpoint': [],
            'current': [],
            'error': [],
            'pid_output': [],
            'pwm': []
        }
        
        # Clear chart curves
        for i in range(4):
            self.setpoint_curves[i].setData([], [])
            self.current_curves[i].setData([], [])
            self.pwm_curves[i].setData([], [])


class ArtificialHorizon(QWidget):
    """Artificial Horizon widget to display pitch and roll."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pitch = 0.0  # Degrees
        self.roll = 0.0   # Degrees
        self.setMinimumSize(200, 200)
        
    def set_attitude(self, pitch, roll):
        """Set pitch and roll in degrees."""
        self.pitch = pitch
        self.roll = roll
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) / 2 - 10
        
        # Clip to circle
        # path = QPainter(self).window() # Dummy path
        # Actually, let's just draw a circle background
        
        painter.translate(center_x, center_y)
        
        # Rotate for roll
        painter.rotate(-self.roll)
        
        # Pitch displacement (approximate pixels per degree)
        pitch_pixels = self.pitch * (radius / 45.0) # 45 degrees = radius
        
        # Draw Sky
        painter.setBrush(QBrush(QColor(100, 150, 255))) # Sky Blue
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(int(-width), int(-height - pitch_pixels), int(2*width), int(height))
        
        # Draw Ground
        painter.setBrush(QBrush(QColor(100, 50, 0))) # Brown
        painter.drawRect(int(-width), int(0 - pitch_pixels), int(2*width), int(height))
        
        # Draw Horizon Line
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.drawLine(int(-width), int(-pitch_pixels), int(width), int(-pitch_pixels))
        
        # Reset rotation for fixed elements
        painter.rotate(self.roll)
        
        # Draw fixed aircraft reference
        painter.setPen(QPen(Qt.GlobalColor.yellow, 3))
        # Left wing
        painter.drawLine(-40, 0, -10, 0)
        painter.drawLine(-10, 0, -10, 10)
        # Right wing
        painter.drawLine(10, 0, 40, 0)
        painter.drawLine(10, 0, 10, 10)
        # Center dot
        painter.drawPoint(0, 0)
        
        # Draw border
        painter.setPen(QPen(Qt.GlobalColor.black, 4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(int(-radius), int(-radius), int(2*radius), int(2*radius))

class CompassWidget(QWidget):
    """Compass widget to display heading."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.heading = 0.0  # Degrees
        self.setMinimumSize(200, 200)
        
    def set_heading(self, heading):
        """Set heading in degrees."""
        self.heading = heading
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) / 2 - 10
        
        painter.translate(center_x, center_y)
        
        # Draw compass rose
        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(int(-radius), int(-radius), int(2*radius), int(2*radius))
        
        # Draw ticks and labels
        for i in range(0, 360, 30):
            painter.save()
            painter.rotate(i - self.heading)
            
            if i % 90 == 0:
                # Major cardinal points
                painter.drawLine(0, int(-radius), 0, int(-radius + 15))
                
                # Draw text
                label = ""
                if i == 0: label = "N"
                elif i == 90: label = "E"
                elif i == 180: label = "S"
                elif i == 270: label = "W"
                
                painter.translate(0, -radius + 25)
                painter.rotate(-(i - self.heading)) # Rotate text back to be upright
                font = painter.font()
                font.setBold(True)
                font.setPointSize(12)
                painter.setFont(font)
                
                # Center text
                fm = painter.fontMetrics()
                text_width = fm.horizontalAdvance(label)
                text_height = fm.height()
                painter.drawText(int(-text_width/2), int(text_height/4), label)
                
            else:
                # Minor ticks
                painter.drawLine(0, int(-radius), 0, int(-radius + 8))
                
            painter.restore()
            
        # Draw fixed heading indicator (triangle at top)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(Qt.GlobalColor.red))
        triangle = QPolygonF([
            QPointF(0, -radius - 5),
            QPointF(-10, -radius - 20),
            QPointF(10, -radius - 20)
        ])
        painter.drawPolygon(triangle)
        
        # Draw current heading text in center
        painter.setPen(QPen(Qt.GlobalColor.black))
        font = painter.font()
        font.setPointSize(16)
        painter.setFont(font)
        heading_str = f"{int(self.heading)}°"
        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(heading_str)
        painter.drawText(int(-text_width/2), 5, heading_str)

class IMUTab(QWidget):
    """IMU Data tab with real-time IMU sensor values."""
    
    startUdpRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.imu_data = []  # List of [imu_id, packet_num, val1, val2, ...]
        self.max_points = 100  # Maximum points to keep
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Controls
        controls_layout = QHBoxLayout()
        self.start_udp_btn = QPushButton("Start Odometry UDP server")
        self.start_udp_btn.clicked.connect(self.on_start_udp_clicked)
        controls_layout.addWidget(self.start_udp_btn)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # Splitter for Horizon and Chart
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Top part: Artificial Horizon and Text Data
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        
        self.horizon = ArtificialHorizon()
        top_layout.addWidget(self.horizon)
        
        self.compass = CompassWidget()
        top_layout.addWidget(self.compass)
        
        # IMU data display (Text)
        # self.imu_label = QLabel("IMU Data: Waiting for data...")
        # self.imu_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        # self.imu_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # top_layout.addWidget(self.imu_label)
        
        splitter.addWidget(top_widget)
        
        # Bottom part: Chart
        self.setup_chart()
        splitter.addWidget(self.chart_widget)
        
        layout.addWidget(splitter)
    
    def on_start_udp_clicked(self):
        self.startUdpRequested.emit()
        self.start_udp_btn.setEnabled(False)  # Disable button after click
        self.start_udp_btn.setText("UDP Server Requested")
        
    def setup_chart(self):
        """Setup chart for IMU values."""
        self.chart_widget = pg.PlotWidget()
        self.chart_widget.setBackground('w')
        self.chart_widget.setTitle("IMU Accelerometer Values")
        self.chart_widget.setLabel('left', 'Value')
        self.chart_widget.setLabel('bottom', 'Packet Number')
        
        # Create curves for different IMU values (only accel x,y,z)
        self.imu_curves = []
        colors = ['red', 'green', 'blue']
        names = ['Accel X', 'Accel Y', 'Accel Z']
        
        for i in range(3):
            curve = self.chart_widget.plot(pen=pg.mkPen(color=colors[i], width=2), name=names[i])
            self.imu_curves.append(curve)
        
        self.chart_widget.addLegend()
        
    def update_data(self, imu_data: list):
        """Update IMU data display."""
        if not imu_data or len(imu_data) < 3:
            return
        
        imu_id, packet_num = imu_data[0], imu_data[1]
        values = imu_data[2:]
        
        # Update label
        values_str = ', '.join(f"{v:.3f}" for v in values)
        # self.imu_label.setText(f"IMU ID: {imu_id}\nPacket: {packet_num}\nValues: [{values_str}]")
        
        # Update Artificial Horizon if quaternion data is available
        # Data format: ID, PacketNum, Accel(3), Gyro(3), Quat(4)
        # Quat indices in values list: 6, 7, 8, 9 (since values starts at index 2 of imu_data)
        if len(values) >= 10:
            w = values[6]
            x = values[7]
            y = values[8]
            z = values[9]
            
            # Convert Quaternion to Euler Angles (Roll, Pitch)
            # Roll (x-axis rotation)
            sinr_cosp = 2 * (w * y + x * z)
            cosr_cosp = 1 - 2 * (y * y + x * x)
            roll = math.atan2(sinr_cosp, cosr_cosp)
            
            # Pitch (y-axis rotation)
            sinp = 2 * (w * x - z * y)
            if abs(sinp) >= 1:
                pitch = math.copysign(math.pi / 2, sinp) # use 90 degrees if out of range
            else:
                pitch = math.asin(sinp)
                
            # Convert to degrees
            roll_deg = math.degrees(roll)
            pitch_deg = math.degrees(pitch)
            
            self.horizon.set_attitude(pitch_deg, roll_deg)
            
            # Yaw (z-axis rotation)
            siny_cosp = 2 * (w * z + x * y)
            cosy_cosp = 1 - 2 * (y * y + z * z)
            yaw = math.atan2(siny_cosp, cosy_cosp)
            yaw_deg = math.degrees(yaw)
            
            # Normalize to 0-360
            if yaw_deg < 0:
                yaw_deg += 360
                
            self.compass.set_heading(yaw_deg)
        
        # Store data
        self.imu_data.append(imu_data)
        if len(self.imu_data) > self.max_points:
            self.imu_data.pop(0)
        
        # Update chart
        if len(self.imu_data) > 0:
            packet_nums = [d[1] for d in self.imu_data]
            for i in range(3):
                if i < len(values):
                    vals = [d[2+i] if len(d) > 2+i else 0 for d in self.imu_data]
                    self.imu_curves[i].setData(packet_nums, vals)
                else:
                    self.imu_curves[i].setData([], [])


class DashboardPanel(QWidget):
    """Dashboard panel with tabbed interface."""
    
    startUdpRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        
        # PID Regulator tab
        self.pid_tab = PIDRegulatorTab()
        self.tab_widget.addTab(self.pid_tab, "PID Regulator")
        
        # IMU Data tab
        self.imu_tab = IMUTab()
        self.imu_tab.startUdpRequested.connect(self.startUdpRequested.emit)
        self.tab_widget.addTab(self.imu_tab, "IMU Data")
        
        # Log PID Analysis tab
        self.log_pid_tab = LogPIDTab()
        self.tab_widget.addTab(self.log_pid_tab, "Log PID Analysis")
        
        layout.addWidget(self.tab_widget)
        
    def update_imu_data(self, imu_data: list):
        """Update IMU data display."""
        self.imu_tab.update_data(imu_data)
        
    def update_chart_data(self, setpoints, encoder_values, time_elapsed):
        """Update PID regulator chart with new data."""
        self.pid_tab.update_data(setpoints, encoder_values, time_elapsed)
        
    def clear_chart_data(self):
        """Clear all chart data."""
        self.pid_tab.clear_data()
        
    def set_ecu_connector(self, ecu_connector):
        """Set ECU connector reference if needed."""
        self.ecu_connector = ecu_connector
        # Propagate adapter to PID tab so tick changes are applied to adapter
        if hasattr(self, 'pid_tab') and hasattr(self.pid_tab, 'set_ecu_connector'):
            self.pid_tab.set_ecu_connector(ecu_connector)
    
    def on_max_rpm_changed(self, max_rpm: int):
        """Update chart Y-axis range when max RPM changes."""
        if hasattr(self, 'pid_tab'):
            self.pid_tab.update_y_axis_range(max_rpm)

