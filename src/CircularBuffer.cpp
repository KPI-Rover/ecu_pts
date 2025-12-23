#include "CircularBuffer.h"

#include <cstring>

CircularBuffer::CircularBuffer(size_t size)
    : size_(size), mask_(size - 1), count_(0), head_(0), tail_(0) {
  buffer_.resize(size);
}

void CircularBuffer::Push(const uint8_t* data, size_t len) {
  size_t space_at_end = size_ - head_;
  size_t first_chunk = (len < space_at_end) ? len : space_at_end;

  memcpy(&buffer_[head_], data, first_chunk);
  if (len > first_chunk) {
    memcpy(&buffer_[0], data + first_chunk, len - first_chunk);
  }

  head_ = (head_ + len) & mask_;

  if (count_ + len > size_) {
    size_t overflow = (count_ + len) - size_;
    tail_ = (tail_ + overflow) & mask_;
    count_ = size_;
  } else {
    count_ += len;
  }
}

void CircularBuffer::Pop(size_t n) {
  if (n > count_) n = count_;
  tail_ = (tail_ + n) & mask_;
  count_ -= n;
}

uint8_t CircularBuffer::Peek(size_t offset) const {
  return buffer_[(tail_ + offset) & mask_];
}

size_t CircularBuffer::Size() const { return count_; }

size_t CircularBuffer::Capacity() const { return size_; }

void CircularBuffer::Clear() {
  head_ = 0;
  tail_ = 0;
  count_ = 0;
}
