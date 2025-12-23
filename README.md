# ECU PTS - Performance Testing Software (C++)

## Starting the Application

To start the Qt6-based motor control GUI application:

1. Navigate to the project root directory (`/home/holy/prj/kpi-rover/ecu_pts`).

2. Build the C++ application:
   ```
   mkdir build
   cd build
   cmake ..
   make
   ```

3. Run the application:
   ```
   ./ecu_pts_cpp
   ```

   This will launch the GUI window for controlling the rover motors. Ensure the rover is accessible at the configured serial port (default: /dev/ttyUSB0 at 115200 baud).

## Features

- Serial communication with ECU
- Motor speed control with sliders
- Real-time RPM monitoring via charts
- Configurable encoder ticks per revolution
- Max RPM limits for control and display

## Requirements

- Qt6 (with Charts)
- CMake
- C++17 compiler
- Linux environment




