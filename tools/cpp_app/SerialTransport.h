#pragma once

#include <atomic>
#include <string>
#include <termios.h>
#include <thread>
#include <vector>

#include "CircularBuffer.h"
#include "ThreadSafeQueue.h"

/**
 * @brief Handles serial communication with a specific protocol.
 *
 * This class manages reading and writing to a serial port using a dedicated
 * read thread and write thread. It implements a specific protocol where
 * frames are structured as: [0xAA] [Length] [Payload] [CRC_L] [CRC_H].
 */
class SerialTransport {
 public:
  /**
   * @brief Constructs a SerialTransport object.
   *
   * @param port The serial port device path (e.g., "/dev/ttyUSB0").
   * @param baud The baud rate for the connection (e.g., 115200).
   * @throws std::runtime_error If the port cannot be opened or configured.
   */
  SerialTransport(const std::string& port, int baud);

  /**
   * @brief Destroys the SerialTransport object.
   *
   * Stops the threads and closes the serial port.
   */
  ~SerialTransport();

  /**
   * @brief Starts the read and write threads.
   *
   * If the transport is already running, this method does nothing.
   */
  void Start();

  /**
   * @brief Stops the read and write threads.
   *
   * Joins the threads if they are joinable.
   */
  void Stop();

  /**
   * @brief Queues data to be sent over the serial port.
   *
   * The input data is expected to be in the format: [Length] [Payload...].
   * This method performs the following operations:
   * 1. Updates the Length byte (data[0]) to match the full frame size.
   * 2. Prepends the start byte (0xAA).
   * 3. Calculates and appends the CRC16 checksum.
   *
   * @param data The data vector containing the length byte and payload.
   */
  void Send(std::vector<uint8_t> data);

  /**
   * @brief Reads a valid packet from the input queue.
   *
   * @param payload Reference to a vector where the extracted payload will be stored.
   * @return true If a packet was successfully retrieved.
   * @return false If the queue was empty.
   */
  bool Read(std::vector<uint8_t>& payload);

 private:
  /**
   * @brief The main loop for the read thread.
   *
   * Continuously reads raw bytes from the serial port and pushes them into
   * the input circular buffer.
   */
  void ReadLoop();

  /**
   * @brief The main loop for the write thread.
   *
   * Continuously pops frames from the output queue and writes them to the
   * serial port.
   */
  void WriteLoop();

  /**
   * @brief Processes the input circular buffer to extract valid frames.
   *
   * Scans the buffer for the start byte (0xAA), validates the length and CRC,
   * and pushes valid payloads to the input queue.
   */
  void ProcessBuffer();

  /**
   * @brief Calculates the CRC16-Modbus checksum.
   *
   * @param data Pointer to the data buffer.
   * @param len Length of the data.
   * @return uint16_t The calculated CRC16 value.
   */
  uint16_t CalculateCrc16(const uint8_t* data, size_t len);

  /**
   * @brief Converts an integer baud rate to the corresponding speed_t constant.
   *
   * @param baud The integer baud rate.
   * @return speed_t The corresponding termios speed constant (e.g., B115200).
   */
  speed_t GetBaud(int baud);

  std::string port_;
  int baud_;
  int fd_ = -1;
  std::atomic<bool> running_{false};

  std::thread read_thread_;
  std::thread write_thread_;

  CircularBuffer input_buffer_;
  ThreadSafeQueue<std::vector<uint8_t>> input_queue_;
  ThreadSafeQueue<std::vector<uint8_t>> output_queue_;
};
