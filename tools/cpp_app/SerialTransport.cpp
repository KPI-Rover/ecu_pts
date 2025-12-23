#include "SerialTransport.h"

#include <fcntl.h>
#include <unistd.h>

#include <cstring>
#include <iostream>
#include <stdexcept>

SerialTransport::SerialTransport(const std::string& port, int baud)
    : port_(port), baud_(baud), input_buffer_(65536) {
  fd_ = open(port.c_str(), O_RDWR | O_NOCTTY | O_SYNC);
  if (fd_ < 0) {
    throw std::runtime_error("Error opening serial port");
  }

  struct termios tty;
  if (tcgetattr(fd_, &tty) != 0) {
    close(fd_);
    throw std::runtime_error("Error getting serial attributes");
  }

  cfsetospeed(&tty, GetBaud(baud));
  cfsetispeed(&tty, GetBaud(baud));

  tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;
  tty.c_cflag |= (CLOCAL | CREAD);
  tty.c_cflag &= ~(PARENB | PARODD);
  tty.c_cflag &= ~CSTOPB;
  tty.c_cflag &= ~CRTSCTS;

  tty.c_iflag &=
      ~(IGNBRK | BRKINT | PARMRK | ISTRIP | INLCR | IGNCR | ICRNL | IXON);
  tty.c_lflag &= ~(ECHO | ECHONL | ICANON | ISIG | IEXTEN);
  tty.c_oflag &= ~OPOST;

  tty.c_cc[VMIN] = 0;
  tty.c_cc[VTIME] = 1;

  if (tcsetattr(fd_, TCSANOW, &tty) != 0) {
    close(fd_);
    throw std::runtime_error("Error setting serial attributes");
  }
}

SerialTransport::~SerialTransport() {
  Stop();
  if (fd_ >= 0) close(fd_);
}

void SerialTransport::Start() {
  if (running_) return;
  running_ = true;
  read_thread_ = std::thread(&SerialTransport::ReadLoop, this);
  write_thread_ = std::thread(&SerialTransport::WriteLoop, this);
}

void SerialTransport::Stop() {
  running_ = false;
  if (read_thread_.joinable()) read_thread_.join();
  if (write_thread_.joinable()) write_thread_.join();
}

void SerialTransport::Send(std::vector<uint8_t> data) {
  if (data.empty()) {
    return;
  }

  // Update Length byte
  // Protocol: Length = 1 (LenByte) + PayloadSize + 2 (CRC)
  // data contains [LenByte] [Payload...]
  // PayloadSize = data.size() - 1
  // New Length = 1 + (data.size() - 1) + 2 = data.size() + 2

  if (data.size() + 2 > 255) {
    return;
  }

  data[0] = static_cast<uint8_t>(data.size() + 2);

  uint16_t crc = CalculateCrc16(data.data(), data.size());

  std::vector<uint8_t> frame;
  frame.reserve(1 + data.size() + 2);
  frame.push_back(0xAA);
  frame.insert(frame.end(), data.begin(), data.end());
  frame.push_back(crc & 0xFF);
  frame.push_back((crc >> 8) & 0xFF);

  output_queue_.Push(frame);
}

bool SerialTransport::Read(std::vector<uint8_t>& payload) {
  return input_queue_.Pop(payload);
}

void SerialTransport::ReadLoop() {
  uint8_t tmp[4096];
  while (running_) {
    int n = ::read(fd_, tmp, sizeof(tmp));
    if (n > 0) {
      input_buffer_.Push(tmp, n);
      ProcessBuffer();
    } else {
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
  }
}

void SerialTransport::WriteLoop() {
  while (running_) {
    std::vector<uint8_t> frame;
    if (output_queue_.Pop(frame)) {
      size_t written = 0;
      while (written < frame.size()) {
        int n = ::write(fd_, frame.data() + written, frame.size() - written);
        if (n > 0) {
          written += n;
        } else {
          std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
      }
    } else {
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
  }
}

void SerialTransport::ProcessBuffer() {
  while (input_buffer_.Size() >= 2) {
    if (input_buffer_.Peek(0) != 0xAA) {
      input_buffer_.Pop(1);
      continue;
    }

    uint8_t len_byte = input_buffer_.Peek(1);
    if (len_byte < 3) {
      input_buffer_.Pop(1);
      continue;
    }

    size_t total_len = 1 + len_byte;

    if (input_buffer_.Size() < total_len) {
      break;
    }

    std::vector<uint8_t> frame(total_len);
    for (size_t i = 0; i < total_len; ++i) {
      frame[i] = input_buffer_.Peek(i);
    }

    uint16_t received_crc = frame[total_len - 2] | (frame[total_len - 1] << 8);
    uint16_t calculated_crc = CalculateCrc16(&frame[1], len_byte - 2);

    if (received_crc == calculated_crc) {
      std::vector<uint8_t> payload;
      if (len_byte > 3) {
        payload.assign(frame.begin() + 2, frame.end() - 2);
      }
      input_queue_.Push(payload);
      input_buffer_.Pop(total_len);
    } else {
      input_buffer_.Pop(1);
    }
  }
}

uint16_t SerialTransport::CalculateCrc16(const uint8_t* data, size_t len) {
  uint16_t crc = 0xFFFF;
  for (size_t pos = 0; pos < len; pos++) {
    crc ^= (uint16_t)data[pos];
    for (int i = 8; i != 0; i--) {
      if ((crc & 0x0001) != 0) {
        crc >>= 1;
        crc ^= 0xA001;
      } else {
        crc >>= 1;
      }
    }
  }
  return crc;
}

speed_t SerialTransport::GetBaud(int baud) {
  switch (baud) {
    case 9600:
      return B9600;
    case 19200:
      return B19200;
    case 38400:
      return B38400;
    case 57600:
      return B57600;
    case 115200:
      return B115200;
    case 230400:
      return B230400;
    case 460800:
      return B460800;
    case 500000:
      return B500000;
    case 921600:
      return B921600;
    case 1000000:
      return B1000000;
    default:
      return B115200;
  }
}
