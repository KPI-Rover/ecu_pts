#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

/**
 * @brief A fixed-size circular buffer implementation.
 *
 * This class provides a high-performance ring buffer for storing bytes.
 * It supports pushing and popping data in chunks and peeking at offsets.
 * The size of the buffer is fixed at construction.
 */
class CircularBuffer {
 public:
  /**
   * @brief Constructs a CircularBuffer with a specified size.
   *
   * @param size The capacity of the buffer in bytes.
   */
  CircularBuffer(size_t size);

  /**
   * @brief Pushes data into the buffer.
   *
   * If the buffer is full, the oldest data will be overwritten (overflow).
   *
   * @param data Pointer to the data to push.
   * @param len Length of the data in bytes.
   */
  void Push(const uint8_t* data, size_t len);

  /**
   * @brief Removes data from the buffer.
   *
   * Advances the tail pointer. If n is greater than the current count,
   * the buffer is emptied.
   *
   * @param n The number of bytes to remove.
   */
  void Pop(size_t n);

  /**
   * @brief Peeks at a byte at a specific offset from the tail.
   *
   * Does not remove the byte from the buffer.
   *
   * @param offset The offset from the current tail (0 is the oldest byte).
   * @return uint8_t The byte at the specified offset.
   */
  uint8_t Peek(size_t offset) const;

  /**
   * @brief Returns the number of bytes currently in the buffer.
   *
   * @return size_t The number of bytes.
   */
  size_t Size() const;

  /**
   * @brief Returns the total capacity of the buffer.
   *
   * @return size_t The capacity in bytes.
   */
  size_t Capacity() const;

  /**
   * @brief Clears the buffer.
   *
   * Resets head, tail, and count to 0.
   */
  void Clear();

 private:
  std::vector<uint8_t> buffer_;
  size_t head_;
  size_t tail_;
  size_t count_;
  size_t size_;
  size_t mask_;
};
