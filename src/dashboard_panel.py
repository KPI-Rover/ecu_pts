from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QHBoxLayout, QGroupBox, QCheckBox, QLabel, QSpinBox, QSplitter, QFileDialog, QPushButton, QProgressBar, QComboBox
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QDateTimeAxis
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QDateTime
from PyQt6.QtGui import QPen, QColor
import pyqtgraph as pg  # For better chart performance
import numpy as np
import re
import logging


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


class DashboardPanel(QWidget):
    """Dashboard panel with tabbed interface."""
    
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
        
        # Log PID Analysis tab
        self.log_pid_tab = LogPIDTab()
        self.tab_widget.addTab(self.log_pid_tab, "Log PID Analysis")
        
        layout.addWidget(self.tab_widget)
        
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

