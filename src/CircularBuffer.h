#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

class CircularBuffer {
 public:
  CircularBuffer(size_t size);
  void Push(const uint8_t* data, size_t len);
  void Pop(size_t n);
  uint8_t Peek(size_t offset) const;
  size_t Size() const;
  size_t Capacity() const;
  void Clear();

 private:
  std::vector<uint8_t> buffer_;
  size_t head_;
  size_t tail_;
  size_t count_;
  size_t size_;
  size_t mask_;
};
