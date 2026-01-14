# ECU PTS - Production Testing Software

The **ECU Production Testing Software (PTS)** is a Linux desktop application designed to interface with the KPI Rover's chassis controller. It provides a comprehensive suite of tools for real-time telemetry monitoring, motor calibration, and protocol debugging.

This software was fully written by **GitHub Copilot** based on the requirements specified in [doc/srs.md](doc/srs.md).

## Install required packages
To build this project on Ubuntu, you need to install the following packages:
```bash
sudo apt update
sudo apt install build-essential cmake qt6-base-dev libqt6charts6-dev
```

## Build
```bash
./build.sh
```

## Run
```bash
./build/ecu_pts
```
