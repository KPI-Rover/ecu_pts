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

  if (data.size() + 2 > 255) {
    return;
  }

  // The protocol expects:
  // [0xAA] [Length] [Payload...] [CRC_L] [CRC_H]
  // Length includes Payload + CRC (2 bytes)
  
  // The reference implementation (tools/cpp_app/SerialTransport.cpp) does:
  // data[0] = static_cast<uint8_t>(data.size() + 2);
  // This implies that the caller MUST reserve the first byte for length!
  
  // However, my ECUConnector implementation does NOT reserve the first byte.
  // It sends [CmdID, Args...].
  
  // So I must PREPEND the length byte.
  
  // BUT, wait. If I prepend length, then the vector becomes:
  // [Length, CmdID, Args...]
  
  // The reference implementation calculates CRC on 'data':
  // uint16_t crc = CalculateCrc16(data.data(), data.size());
  // So CRC is calculated on [Length, CmdID, Args...] (assuming data[0] was length).
  
  // My previous fix:
  // payload_with_len = [Length, CmdID, Args...]
  // crc = CalculateCrc16(payload_with_len...)
  // frame = [0xAA, Length, CmdID, Args..., CRC_L, CRC_H]
  
  // This looks correct IF the ECU expects CRC to cover Length.
  
  // Let's look at the log again.
  // "CRC mismatch on serial frame"
  
  // Maybe the ECU expects CRC to cover ONLY the payload (CmdID + Args)?
  // Or maybe it expects CRC to cover [0xAA, Length, Payload...]?
  
  // Let's check ProcessBuffer in SerialTransport.cpp (which mimics ECU logic?)
  /*
    uint16_t received_crc = frame[total_len - 2] | (frame[total_len - 1] << 8);
    uint16_t calculated_crc = CalculateCrc16(&frame[1], len_byte - 2);
    
    if (received_crc == calculated_crc) { ... }
  */
  
  // frame[0] is 0xAA.
  // frame[1] is Length.
  // &frame[1] points to Length.
  // len_byte is the value of Length byte.
  // len_byte = PayloadSize + 2 (CRC size).
  // CalculateCrc16 is called with length: len_byte - 2.
  // So it calculates CRC on (PayloadSize + 2) - 2 = PayloadSize bytes.
  // STARTING AT &frame[1].
  
  // Wait!
  // If frame is [AA, Len, Pay0, Pay1, CRC, CRC]
  // &frame[1] is Len.
  // It calculates CRC on 'Len' and following bytes?
  
  // If len_byte is 4 (1 byte payload + 2 crc).
  // It calculates CRC on 4-2 = 2 bytes.
  // Starting at frame[1].
  // So it calculates CRC on [Len, Pay0].
  
  // So YES, CRC includes the Length byte!
  
  // My previous fix:
  // payload_with_len = [Length, CmdID, Args...]
  // crc = CalculateCrc16(payload_with_len...)
  // This matches the logic: CRC on [Length, Payload...].
  
  // So why mismatch?
  
  // Maybe the length calculation is wrong?
  // data.size() is Payload size.
  // Length = data.size() + 2.
  
  // Example: GetApiVersion (0x01, 0x01). Payload size 2.
  // Length = 4.
  // payload_with_len = [0x04, 0x01, 0x01].
  // CRC on [0x04, 0x01, 0x01].
  
  // Wait, ProcessBuffer logic:
  // uint16_t calculated_crc = CalculateCrc16(&frame[1], len_byte - 2);
  
  // If len_byte is 4.
  // It calculates CRC on 2 bytes.
  // Starting at frame[1] (which is 0x04).
  // So it calculates CRC on [0x04, 0x01].
  // It MISSES the last byte of payload (0x01)!
  
  // If len_byte includes CRC size (2 bytes).
  // And we want to calculate CRC on [Length, Payload...].
  // The size of [Length, Payload...] is 1 + PayloadSize.
  // len_byte = PayloadSize + 2.
  // We want to calculate on 1 + PayloadSize bytes.
  // 1 + PayloadSize = 1 + (len_byte - 2) = len_byte - 1.
  
  // But ProcessBuffer uses `len_byte - 2`.
  // This means it calculates CRC on `PayloadSize` bytes.
  // Starting at `frame[1]` (Length).
  // So it calculates CRC on [Length, Payload[0]... Payload[N-2]].
  // It effectively drops the last byte of the payload from CRC calculation?
  // OR, it implies Length byte is NOT part of CRC, and &frame[1] is wrong?
  
  // If the reference implementation `tools/cpp_app/SerialTransport.cpp` is correct (it's from the repo),
  // then `CalculateCrc16(&frame[1], len_byte - 2)` is the ground truth for RX.
  
  // Let's trace the TX side of reference implementation:
  // data[0] = static_cast<uint8_t>(data.size() + 2);
  // crc = CalculateCrc16(data.data(), data.size());
  
  // Here `data` ALREADY has length at index 0.
  // So `data.size()` is the full size of vector passed to Send.
  // Let's say caller passes vector of size 3: [Dummy, Pay1, Pay2].
  // data[0] becomes 3+2 = 5.
  // Vector: [0x05, Pay1, Pay2].
  // CRC calc on 3 bytes: [0x05, Pay1, Pay2].
  
  // RX side:
  // frame: [AA, 05, Pay1, Pay2, CRC, CRC].
  // len_byte = 5.
  // Calc CRC on `len_byte - 2` = 3 bytes.
  // Starting at `frame[1]` (0x05).
  // Bytes: 0x05, Pay1, Pay2.
  
  // This matches!
  
  // So my logic for TX seems correct:
  // payload_with_len = [Length, Payload...]
  // CRC on payload_with_len.
  
  // So why mismatch?
  
  // Maybe `data.size()` in `payload_with_len.push_back` is wrong?
  // `data` is [CmdID, Args...].
  // `data.size()` is PayloadSize.
  // `payload_with_len` gets `PayloadSize + 2`.
  // Then `data` is appended.
  // So `payload_with_len` is [Len, CmdID, Args...].
  // Size is 1 + PayloadSize.
  
  // In reference TX:
  // Caller passes `data` where `data[0]` is reserved.
  // `data.size()` includes the reserved byte.
  // So `data.size()` = 1 + PayloadSize.
  // `data[0]` = (1 + PayloadSize) + 2 = PayloadSize + 3?
  // NO!
  
  // If reference TX says: `data[0] = data.size() + 2`.
  // And `data` is [Reserved, Pay1, Pay2]. Size 3.
  // `data[0]` = 5.
  // But PayloadSize is 2.
  // Length should be PayloadSize + CRC = 2 + 2 = 4?
  // Or does Length include Length byte itself?
  
  // If `data[0]` = 5.
  // RX sees len=5.
  // RX expects total_len = 1 + 5 = 6 bytes. [AA, 05, Pay1, Pay2, CRC, CRC].
  // Payload is Pay1, Pay2. Size 2.
  // CRC is 2.
  // Length byte is 1.
  // Total 5 bytes (excluding AA).
  // So Length = 1 (Len) + 2 (Pay) + 2 (CRC) = 5.
  
  // So Length INCLUDES the Length byte itself!
  
  // My code:
  // payload_with_len.push_back(static_cast<uint8_t>(data.size() + 2));
  // `data.size()` is PayloadSize.
  // I am setting Length = PayloadSize + 2.
  // I am MISSING the +1 for the Length byte itself!
  
  // Let's verify.
  // My code: Payload [0x01, 0x01] (Size 2).
  // Length = 2 + 2 = 4.
  // Frame: [AA, 04, 01, 01, CRC, CRC].
  // RX sees Len=4.
  // RX expects total_len = 1 + 4 = 5 bytes.
  // But we sent 6 bytes! [AA, 04, 01, 01, CRC, CRC].
  // RX reads AA, 04.
  // RX reads 4-2 = 2 bytes for CRC calc?
  // RX reads frame of size 5: [AA, 04, 01, 01, CRC_L].
  // CRC_H is left in buffer!
  // CRC check fails because it reads wrong bytes for CRC.
  
  // FIX: Length should be `data.size() + 3` (Payload + CRC + LengthByte).
  
  uint8_t len_byte = static_cast<uint8_t>(data.size() + 3);
  
  std::vector<uint8_t> payload_with_len;
  payload_with_len.reserve(1 + data.size());
  payload_with_len.push_back(len_byte);
  payload_with_len.insert(payload_with_len.end(), data.begin(), data.end());
  
  uint16_t crc = CalculateCrc16(payload_with_len.data(), payload_with_len.size());

  std::vector<uint8_t> frame;
  frame.reserve(1 + payload_with_len.size() + 2);
  frame.push_back(0xAA);
  frame.insert(frame.end(), payload_with_len.begin(), payload_with_len.end());
  frame.push_back(crc & 0xFF);
  frame.push_back((crc >> 8) & 0xFF);

  output_queue_.Push(frame);
  if (log_cb_) log_cb_(frame, true);
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
      if (log_cb_) log_cb_(frame, false);
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
