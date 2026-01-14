#pragma once

#include <atomic>
#include <string>
#include <termios.h>
#include <thread>
#include <vector>
#include <functional>

#include "CircularBuffer.h"
#include "ThreadSafeQueue.h"

class SerialTransport {
 public:
  SerialTransport(const std::string& port, int baud);
  ~SerialTransport();

  using LogCallback = std::function<void(const std::vector<uint8_t>&, bool isTx)>;
  void SetLogCallback(LogCallback cb) { log_cb_ = cb; }

  void Start();
  void Stop();
  void Send(std::vector<uint8_t> data);
  bool Read(std::vector<uint8_t>& payload);
  bool IsConnected() const { return fd_ >= 0; }

 private:
  void ReadLoop();
  void WriteLoop();
  void ProcessBuffer();
  uint16_t CalculateCrc16(const uint8_t* data, size_t len);
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
  LogCallback log_cb_;
};
