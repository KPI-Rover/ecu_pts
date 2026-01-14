#!/bin/bash

# Exit on error
set -e

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
BUILD_DIR="$SCRIPT_DIR/build"

echo "Using build directory: $BUILD_DIR"

# Remove build directory if it exists to ensure a clean build
if [ -d "$BUILD_DIR" ]; then
    echo "Cleaning old build directory..."
    rm -rf "$BUILD_DIR"
fi

# Create build directory
mkdir -p "$BUILD_DIR"

# Navigate to build directory
cd "$BUILD_DIR"

# Configure the project
echo "Running CMake..."
cmake ..

# Build the project
echo "Building..."
make -j$(nproc)

echo "Build successful!"
echo "To start the program run:"
echo "./build/ecu_pts"
