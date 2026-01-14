# Software Requirements Specification ECU PTS 

## General UI Layout

**[REQ-001]** The UI must be split horizontally into two parts: Dashboard and Control.
   - The Control part must occupy 25% of the window height.
   - The Dashboard part must occupy the remaining 75% of the window height.

## Control Part Requirements

**[REQ-002]** The Control part must consist of three sections arranged horizontally in one line:
   - Connection settings section
   - Sliders section for manual motor control
   - Gamepad/joystick section for robot control

**[REQ-003]** The sliders section must have two main groups: Together mode and Individual mode.

**[REQ-004]** Together mode must include:
   - A checkbox labeled "All motors the same speed".
   - A slider labeled "All motors speed".

**[REQ-005]** Individual mode must include:
   - Four sliders, each for setting the speed of an individual motor.

**[REQ-006]** The Control part must have a field where the user can enter the maximum motor RPM. The default value is 200.

**[REQ-007]** The connection settings section must include:
   - An input field for the Serial port with default value of "/dev/ttyUSB0".
   - An input field for the Baud rate with default value of 115200.
   - A button to connect to/disconnect from the rover.

**[REQ-008]** The range of each slider must be from -max RPM to max RPM, where max RPM is the value entered by the user.

**[REQ-009]** Each slider must visually indicate its minimum, zero, and maximum positions.

**[REQ-010]** Each slider must display its current value next to it, and the value must be editable by the user, updating the slider position accordingly.

**[REQ-011]** The Control part must have a button to stop all motors, which sets all speeds to zero. This button must be painted red.

**[REQ-012]** When "All motors the same speed" is checked:
   - The value from the "All motors speed" slider is sent to all motors.
   - The Individual mode group is disabled (grayed out).

**[REQ-013]** When "All motors the same speed" is unchecked:
   - Each motor's speed can be set independently using the individual sliders.

**[REQ-014]** The Control part must reflect the current mode and synchronize slider values as appropriate.

**[REQ-015]** The gamepad/joystick section must provide visual representation of joystick position for robot control. (Implemented as virtual joystick widget)

**[REQ-016]** The gamepad/joystick section must support both physical gamepad input and virtual on-screen joystick control. (Virtual joystick implemented; physical gamepad not yet supported)

**[REQ-017]** The gamepad/joystick control must translate joystick movements to appropriate motor speed commands for differential drive control. (Implemented: Y-axis for forward/backward, X-axis for turning)

**[REQ-018]** After connecting to the rover, the program should periodically read data and send motor speeds:
   - Default refresh interval should be 100ms.
   - User should be able to adjust this refresh interval.
   - The periodic tasks include sending motor speeds (REQ-019), reading encoder values (REQ-026), and reading IMU data (REQ-033).
   - The periodic sending should stop when disconnected.

**[REQ-019]** Communication protocol with ECU controller must be implemented according to the Сhassis Controller Communication Protocol (protocol.md). Only Serial transport should be implemented.

## Dashboard Requirements

**[REQ-022]** The Dashboard part must be a container for tabs with the following tabs implemented:
   - PID Regulator tab: Provides interface for tuning and monitoring PID controller parameters.
   - Protocol Tester tab: Provides interface for sending manual commands and viewing raw communication logs.
   - IMU tab: Provides visual representation of IMU data (accelerometer, compass, horizon).

### PID Regulator Tab Requirements

**[REQ-023]** The PID Regulator tab must display a chart for each motor showing:
   - Setpoint: Value from the corresponding motor slider.
   - Current value: RPM calculated based on encoder values read from ECU.

**[REQ-024]** The chart must include a legend with the following visual specifications:
   - Dotted line for setpoint values.
   - Solid line for current values.
   - Different colors for each motor (Red, Blue, Green, Orange).

**[REQ-025]** The user must be able to select which motors to display on the chart using checkboxes, which can be combined with the legend for motor selection.

**[REQ-026]** The software must periodically, together with sending motor speeds (REQ-018), read encoder values using the `get_all_encoders` command (as defined in `protocol.md`) to calculate current RPM values for the chart.

**[REQ-027]** User should be able to change number of encoder ticks per one revolution for all motors. The default value is 1328.

**[REQ-028]** User should be able to scroll axis X on the PID Regulator chart. (Implemented: Horizontal rubber band scrolling when auto-scroll is disabled).

**[REQ-029]** User should be able to zoom in/out axis X on the PID Regulator chart. (Implemented: Ctrl+mouse wheel zooms X-axis in/out, mouse wheel scrolls X-axis).

### Protocol Tester Tab Requirements

**[REQ-030]** The Protocol Tester tab must allow selecting and sending any command defined in the communication protocol.

**[REQ-031]** The Protocol Tester tab must display a log of all sent (TX) and received (RX) messages.

**[REQ-032]** For each message in the log, both the high-level description and the raw hexadecimal data (including protocol framing and CRC) must be displayed.

### IMU Tab Requirements

**[REQ-033]** The IMU tab must periodically read IMU data using the `get_imu` command (as defined in `protocol.md`).

**[REQ-034]** The IMU tab must display three real-time charts showing acceleration for X, Y, and Z axes.
   - The axes mapping must account for hardware orientation (Hardware Y mapped to App X, Hardware X mapped to App Y).
   - The Y-axis (acceleration) range must be sufficient to show gravity (e.g., +/- 15 m/s²).

**[REQ-035]** The IMU tab must include visual widgets for orientation:
   - Compass: Shows the current heading (Yaw) derived from quaternion data.
   - Artificial Horizon: Shows the current Roll and Pitch derived from quaternion data.

**[REQ-036]** The IMU tab must be scrollable to accommodate all visualizations on smaller screens.

## Non-Functional Requirements

**[REQ-020]** UI implementation must be separated from functional implementation.

**[REQ-021]** Software should provide detailed log, including raw communication data when enabled in the Protocol Tester.

## Technical Requirements

**[REQ-037]** The software must be developed using the C++17 standard (or later).

**[REQ-038]** The application must be built using the Qt 6 framework, specifically leveraging the Widgets and Charts modules.


