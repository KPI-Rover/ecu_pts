import pytest
from unittest.mock import Mock, patch, call
from src.ecu_connector import ECUConnector, TCPTransport
from src.ecu_connector.command import SetAllMotorsSpeedCommand, SetMotorSpeedCommand, GetApiVersionCommand

@pytest.fixture
def mock_transport():
    return Mock(spec=TCPTransport)

@pytest.fixture
def connector(mock_transport):
    return ECUConnector(mock_transport)

def test_initialization(connector, mock_transport):
    assert isinstance(connector, ECUConnector)
    assert connector._transport == mock_transport

def test_connect_success(connector):
    connector._transport.connect.return_value = True
    result = connector.connect('127.0.0.1', 1234)
    assert result is True
    connector._transport.connect.assert_called_once_with('127.0.0.1', 1234)

def test_connect_failure(connector):
    connector._transport.connect.return_value = False
    result = connector.connect('127.0.0.1', 1234)
    assert result is False

def test_set_callbacks(connector):
    status_cb = Mock()
    error_cb = Mock()
    connector.set_callbacks(status_callback=status_cb, error_callback=error_cb)
    assert connector._status_callback == status_cb
    assert connector._error_callback == error_cb

def test_set_all_motors_speed(connector):
    speeds = [100, 200, 300, 400]
    connector._running = True
    connector.set_all_motors_speed(speeds)
    assert not connector._command_queue.is_empty()
    command = connector._command_queue.pop()
    assert isinstance(command, SetAllMotorsSpeedCommand)
    assert command.speeds == speeds

def test_is_connected(connector, mock_transport):
    mock_transport.is_connected.return_value = True
    connector._running = True
    assert connector.is_connected() is True
    mock_transport.is_connected.return_value = False
    assert connector.is_connected() is False

def test_start_and_stop(connector):
    with patch('threading.Thread') as mock_thread:
        connector.start()
        mock_thread.assert_called_once()
        connector.stop()
        # Assume stop calls transport.disconnect or similar

def test_callback_invocation(connector):
    status_cb = Mock()
    error_cb = Mock()
    connector.set_callbacks(status_callback=status_cb, error_callback=error_cb)
    # Simulate callback triggers (assuming internal logic)
    connector._status_callback("Connected")
    status_cb.assert_called_once_with("Connected")

def test_set_motor_speed(connector):
    connector._running = True
    connector.set_motor_speed(1, 100)
    assert not connector._command_queue.is_empty()
    command = connector._command_queue.pop()
    assert isinstance(command, SetMotorSpeedCommand)
    assert command.motor_id == 1
    assert command.speed == 100

def test_set_motor_speed_not_running(connector):
    connector.set_motor_speed(1, 100)
    assert connector._command_queue.is_empty()

def test_set_all_motors_speed_not_running(connector):
    speeds = [100, 200, 300, 400]
    connector.set_all_motors_speed(speeds)
    assert connector._command_queue.is_empty()

def test_set_all_motors_speed_invalid_length(connector):
    connector._running = True
    speeds = [100, 200, 300]  # Only 3 speeds
    connector.set_all_motors_speed(speeds)
    assert connector._command_queue.is_empty()

def test_disconnect(connector):
    connector._running = True
    connector._worker_thread = Mock()
    connector.disconnect()
    assert connector._running is False
    connector._transport.disconnect.assert_called_once()

def test_get_command_stats(connector):
    connector._total_commands = 5
    connector._failed_commands = 2
    total, failed = connector.get_command_stats()
    assert total == 5
    assert failed == 2

def test_reset_command_stats(connector):
    connector._total_commands = 5
    connector._failed_commands = 2
    connector.reset_command_stats()
    assert connector._total_commands == 0
    assert connector._failed_commands == 0

def test_command_execution_failure():
    mock_transport = Mock()
    mock_transport.send.return_value = False  # Send fails
    command = SetMotorSpeedCommand(1, 100)
    response = command.execute(mock_transport)
    assert response.success is False
    assert "Failed to send" in response.error_message

def test_get_api_version_command():
    mock_transport = Mock()
    mock_transport.send.return_value = True
    mock_transport.receive.return_value = b'\x01\x02'  # Mock response
    command = GetApiVersionCommand()
    response = command.execute(mock_transport)
    assert response.success is True
    assert response.data == b'\x01\x02'
    mock_transport.send.assert_called_once_with(bytes([0x01]))
    mock_transport.receive.assert_called_once_with(2)

def test_get_api_version_command_failure():
    mock_transport = Mock()
    mock_transport.send.return_value = True
    mock_transport.receive.return_value = None  # Receive fails
    command = GetApiVersionCommand()
    response = command.execute(mock_transport)
    assert response.success is False
    assert "Failed to receive" in response.error_message

def test_set_motor_speed_command_binary():
    mock_transport = Mock()
    mock_transport.send.return_value = True
    command = SetMotorSpeedCommand(1, 100)
    response = command.execute(mock_transport)
    assert response.success is True
    # Check sends: command ID 0x02, then motor_id and speed*100 as >Bi
    import struct
    expected_payload = struct.pack('>Bi', 1, 100 * 100)
    mock_transport.send.assert_has_calls([call(bytes([0x02])), call(expected_payload)])

def test_set_all_motors_speed_command_binary():
    mock_transport = Mock()
    mock_transport.send.return_value = True
    speeds = [100, 200, 300, 400]
    command = SetAllMotorsSpeedCommand(speeds)
    response = command.execute(mock_transport)
    assert response.success is True
    # Check sends: command ID 0x03, then each speed*100 as 4-byte big-endian signed
    expected_payload = b''
    for speed in speeds:
        speed_int = speed * 100
        expected_payload += speed_int.to_bytes(4, byteorder='big', signed=True)
    mock_transport.send.assert_has_calls([call(bytes([0x03])), call(expected_payload)])
