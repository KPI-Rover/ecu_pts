# ECU PTS 

## Software Requirements Specification

### General UI Layout

**[REQ-001]** The UI must be split horizontally into two parts: Dashboard and Control.
   - The Control part must occupy 25% of the window height.
   - The Dashboard part must occupy the remaining 75% of the window height.

### Control Part Requirements

**[REQ-002]** The Control part must consist of three sections:
   - Connection settings section
   - Sliders section for manual motor control
   - Gamepad/joystick section for robot control

**[REQ-003]** The sliders section must have two main groups: Together mode and Individual mode.

**[REQ-004]** Together mode must include:
   - A checkbox labeled "All motors the same speed".
   - A slider labeled "All motors speed".

**[REQ-005]** Individual mode must include:
   - Four sliders, each for setting the speed of an individual motor.

**[REQ-006]** The Control part must have a field where the user can enter the maximum motor RPM. The default value is 100.

**[REQ-007]** The connection settings section must include:
   - An input field for the Rover IP address with default value of "10.30.30.30".
   - An input field for the Rover port number with default value of 6000.
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

**[REQ-015]** The gamepad/joystick section must provide visual representation of joystick position for robot control.

**[REQ-016]** The gamepad/joystick section must support both physical gamepad input and virtual on-screen joystick control.

**[REQ-017]** The gamepad/joystick control must translate joystick movements to appropriate motor speed commands for differential drive control.

**[REQ-018]** After connecting to the rover, the program should periodically send motor speeds:
   - Default refresh interval should be 200ms.
   - User should be able to adjust this refresh interval.
   - The periodic sending should stop when disconnected.

**[REQ-019]** Communication protocol with ECU controller must be implemented according to the Сhassis Controller Communication Protocol (protocol.md). Only TCP transport should be implemented.

## Dashboard Requirements

**[REQ-022]** The Dashboard part must be a container for tabs with the following tabs implemented:
   - PID Regulator tab: Provides interface for tuning and monitoring PID controller parameters

### PID Regulator Tab Requirements

**[REQ-023]** The PID Regulator tab must display a chart for each motor showing:
   - Setpoint: Value from the corresponding motor slider
   - Current value: RPM calculated based on encoder values read from ECU

**[REQ-024]** The chart must include a legend with the following visual specifications:
   - Dotted line for setpoint values
   - Solid line for current values
   - Different colors for each motor

**[REQ-025]** The user must be able to select which motors to display on the chart using checkboxes, which can be combined with the legend for motor selection.

**[REQ-026]** The software must periodically, together with sending motor speeds (REQ-018), read encoder values using the get_all_encoders command (as defined in protocol.md) to calculate current RPM values for the chart.

**[REQ-027]** User should be able to change number of encoder ticks per one revolution for each motor separately. The default value is 260.

**[REQ-028]** User should be able to scroll axis X on the PID Regulator chart.

**[REQ-029]** User should be able to zoom in/out axis X on the PID Regulator chart.

## Non-Functional Requirements

**[REQ-020]** UI implementation must be separated from functional implementation.

**[REQ-021]** Software should provide detailed log. It should be possible to adjust log level.

## Software Architecture Design

### Component Overview
The software is divided into three main components:

1. **UI Component**
   - Responsible for rendering and handling user interface
   - Consists of two main parts:
     - **Dashboard Part** (75% height): Displays real-time charts and visualizations
     - **Control Part** (25% height): Contains motor control interface and connection settings
   - Implements UI logic and event handling
   - Interacts directly with ECU Connector through its public interface

2. **ECU Connector Component**
   - Manages communication with chassis controller
   - Implements command queuing and execution
   - Implements transport layer (TCP, future UART support)
   - Handles protocol implementation and transport abstraction
   - Provides high-level interface for motor control operations

3. **Data Management Component**
   - Collects and stores motor speed and status data
   - Provides data to Dashboard for visualization
   - Maintains historical data for charting

### Class Structure

![Component Diagram](sad_components.png)

### Component Interactions

1. **Threading Model**
   - ECUConnector runs in dedicated worker thread
   - UI runs in main thread (both Dashboard and Control parts)
   - Commands are passed through thread-safe queue
   - State changes are propagated to UI thread through signals/callbacks
   - Data updates are pushed to Dashboard for real-time visualization

2. **Command Flow**
   - Control part calls ECUConnector's public methods (thread-safe)
   - Commands are queued for processing
   - Worker thread processes commands sequentially
   - Results are propagated back to UI thread
   - Dashboard receives data updates for visualization

3. **Transport Abstraction**
   - ITransport interface defines common transport operations
   - Concrete implementations (TCP, UART) handle specific protocols
   - ECUConnector uses transport through interface

4. **Error Handling**
   - Transport errors are propagated to ECUConnector
   - ECUConnector manages reconnection and command retries
   - UI is notified of connection state changes

5. **Data Flow**
   - Motor speed commands flow from Control part to ECUConnector
   - Status and telemetry data flow from ECUConnector to Data Management
   - Data Management provides data to Dashboard for visualization
   - Dashboard updates in real-time as new data arrives

### Design Considerations

1. **UI Layout**
   - Split layout with Dashboard (75%) and Control (25%)
   - Dashboard remains responsive during control operations
   - Independent update cycles for Dashboard and Control parts

2. **Command Pattern**
   - Command objects encapsulate protocol operations
   - Commands are queued and executed sequentially within ECUConnector
   - Each command type defines its own timeout and retry behavior

3. **Transport Abstraction**
   - Interface-based design for transport layer
   - Easy to add new transport types
   - Common error handling across transports

4. **Thread Safety**
   - Command queue is thread-safe within ECUConnector using locks and condition variables
   - Transport operations are synchronized to prevent concurrent access
   - UI updates handled in main thread only through Qt's signal/slot mechanism
   - Data Management component uses thread-safe data structures for chart data storage
   - ECU Connector worker thread is isolated from UI thread to prevent blocking
   - All shared data access is protected with appropriate synchronization primitives
   - Periodic operations (motor speed sending, encoder reading) are managed by dedicated timers in UI thread

5. **Thread Management**
   - ECUConnector manages its own worker thread with proper startup/shutdown handling
   - Thread-safe command queue handles inter-thread communication
   - Clean shutdown handling on program exit with thread join operations
   - UI remains responsive during long operations through asynchronous processing
   - Worker thread exception handling prevents crashes from propagating to UI

6. **Data Visualization**
   - Dashboard updates asynchronously from control operations
   - Efficient data buffering for smooth chart rendering
   - Configurable chart update rates independent of control refresh rate
   - Chart data is updated in a thread-safe manner using Qt's signal/slot system

7. **Synchronization Mechanisms**
   - Qt Signals/Slots for thread-safe UI updates
   - Mutex-protected command queues for producer-consumer patterns
   - Atomic operations for simple state variables
   - Event-driven architecture to avoid polling and reduce synchronization overhead
   - Timeout mechanisms for network operations to prevent indefinite blocking

8. **Error Propagation**
   - Errors from worker thread are propagated to UI through callback mechanisms
   - Network timeouts and connection failures are handled gracefully
   - UI provides feedback for all error conditions without blocking the interface
   - Logging system captures thread-specific errors for debugging






