# Test application for chassis controller

## Starting the Application

To start the PyQt5-based motor control GUI application using a virtual environment:

1. Navigate to the project root directory (`/home/holy/prj/kpi-rover/ecu_pts`).

2. Create a virtual environment (if not already created):
   ```
   python -m venv venv
   ```

3. Activate the virtual environment:
   - On Linux/Mac:
     ```
     source venv/bin/activate
     ```
   - On Windows:
     ```
     venv\Scripts\activate
     ```

4. Install required dependencies from the requirements file:
   ```
   pip install -r requirements.txt
   ```
   
   Note: If you encounter issues with PyQt6.QtCharts, you may need to install it separately:
   ```
   pip install PyQt6-Charts
   ```

5. Run the application script:
   ```
   python src/ecu_pts.py
   ```

   This will launch the GUI window for controlling the rover motors. Ensure the rover is accessible at the configured IP and port (default: 10.30.30.30:6000).

6. After use, deactivate the virtual environment:
   ```
   deactivate
   ```

## Running Unit Tests

To run the unit tests for the ECU connector module:

1. Ensure you have pytest installed. If not, install it using pip:
   ```
   pip install -r requirements.txt
   ```

2. Navigate to the project root directory (`/home/holy/prj/kpi-rover/ecu_pts`).

3. Run the tests using pytest:
   ```
   pytest tests/test_ecu_connector.py
   ```

   This will execute all test cases in `test_ecu_connector.py`, providing output on passed/failed tests. For verbose output, add the `-v` flag: `pytest -v tests/test_ecu_connector.py`.
