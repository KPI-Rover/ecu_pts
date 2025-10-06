# ECU PTS 

## Software Requirements Specification

1. The UI must have two main groups: Together mode and Individual mode.
2. Together mode must include:
   - A checkbox labeled "All motors the same speed".
   - A slider labeled "All motors speed".
3. Individual mode must include:
   - Four sliders, each for setting the speed of an individual motor.
4. The UI must have a field where the user can enter the maximum motor RPM. The default value is 100.
5. The UI must include connection settings:
   - An input field for the Rover IP address with default value of "10.30.30.30".
   - An input field for the Rover port number with default value of 6000.
   - A button to connect to/disconnect from the rover.
6. The range of each slider must be from -max RPM to max RPM, where max RPM is the value entered by the user.
7. Each slider must visually indicate its minimum, zero, and maximum positions.
8. Each slider must display its current value next to it, and the value must be editable by the user, updating the slider position accordingly.
9. The UI must have a button to stop all motors, which sets all speeds to zero. This button must be painted red.
10. When "All motors the same speed" is checked:
    - The value from the "All motors speed" slider is sent to all motors.
    - The Individual mode group is disabled (grayed out).
11. When "All motors the same speed" is unchecked:
    - Each motor's speed can be set independently using the individual sliders.
12. The UI must reflect the current mode and synchronize slider values as appropriate.
13. After connecting to the rover, the program should periodically send motor speeds:
    - Default refresh interval should be 200ms.
    - User should be able to adjust this refresh interval.
    - The periodic sending should stop when disconnected.
14. Communication protocol with ECU controller must be implemented according to the Сhassis Controller Communication Protocol (protocol.md). Only TCP transport should be implemented.
15. UI implementation must be separated from functional implementation
16. Software should provide detailed log. It should be possible to adjust log level.

## Software Architecture Design

### Component Overview
The software is divided into two main components:

1. **UI Component**
   - Responsible for rendering and handling user interface
   - Implements UI logic and event handling
   - Interacts directly with ECU Connector through its public interface

2. **ECU Connector Component**
   - Manages communication with chassis controller
   - Implements command queuing and execution
   - Implements transport layer (TCP, future UART support)
   - Handles protocol implementation and transport abstraction
   - Provides high-level interface for motor control operations

### Class Structure

![Component Diagram](sad_components.png)

### Component Interactions

1. **Threading Model**
   - ECUConnector runs in dedicated worker thread
   - UI runs in main thread
   - Commands are passed through thread-safe queue
   - State changes are propagated to UI through signals/callbacks

2. **Command Flow**
   - UI calls ECUConnector's public methods (thread-safe)
   - Commands are queued for processing
   - Worker thread processes commands sequentially
   - Results are propagated back to UI thread

3. **Transport Abstraction**
   - ITransport interface defines common transport operations
   - Concrete implementations (TCP, UART) handle specific protocols
   - ECUConnector uses transport through interface

4. **Error Handling**
   - Transport errors are propagated to ECUConnector
   - ECUConnector manages reconnection and command retries
   - UI is notified of connection state changes

### Design Considerations

1. **Command Pattern**
   - Command objects encapsulate protocol operations
   - Commands are queued and executed sequentially within ECUConnector
   - Each command type defines its own timeout and retry behavior

2. **Transport Abstraction**
   - Interface-based design for transport layer
   - Easy to add new transport types
   - Common error handling across transports

3. **Thread Safety**
   - Command queue is thread-safe within ECUConnector
   - Transport operations are synchronized
   - UI updates handled in main thread

4. **Thread Management**
   - ECUConnector manages its own worker thread
   - Thread-safe command queue handles inter-thread communication
   - Clean shutdown handling on program exit
   - UI remains responsive during long operations






