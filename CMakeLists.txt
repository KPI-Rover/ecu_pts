cmake_minimum_required(VERSION 3.16)

project(ecu_pts VERSION 0.1 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets Charts)

set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

set(SOURCES
    src/main.cpp
    src/MainWindow.cpp
    src/MainWindow.h
    src/ControlPanel.cpp
    src/ControlPanel.h
    src/IMUPanel.cpp
    src/IMUPanel.h
    src/DashboardPanel.cpp
    src/DashboardPanel.h
    src/ProtocolTestPanel.cpp
    src/ProtocolTestPanel.h
    src/ECUConnector.cpp
    src/ECUConnector.h
    src/SerialTransport.cpp
    src/SerialTransport.h
    src/CircularBuffer.cpp
    src/CircularBuffer.h
    src/ThreadSafeQueue.h
    src/VirtualJoystick.cpp
    src/VirtualJoystick.h
    src/resources.qrc
)

add_executable(ecu_pts ${SOURCES})

target_link_libraries(ecu_pts PRIVATE Qt6::Widgets Qt6::Charts)
