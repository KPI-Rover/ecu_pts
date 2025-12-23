#pragma once

#include <condition_variable>
#include <mutex>
#include <queue>

/**
 * @brief A thread-safe queue implementation.
 *
 * This class wraps std::queue with a mutex and condition variable to allow
 * safe concurrent access from multiple threads.
 *
 * @tparam T The type of elements stored in the queue.
 */
template <typename T>
class ThreadSafeQueue {
 public:
  /**
   * @brief Pushes a value onto the queue.
   *
   * Acquires a lock, pushes the value, and notifies one waiting thread.
   *
   * @param value The value to push.
   */
  void Push(const T& value);

  /**
   * @brief Pops a value from the queue if available.
   *
   * Non-blocking. If the queue is empty, returns false immediately.
   *
   * @param value Reference where the popped value will be stored.
   * @return true If a value was popped.
   * @return false If the queue was empty.
   */
  bool Pop(T& value);

  /**
   * @brief Waits for a value to be available and then pops it.
   *
   * Blocking. Waits on a condition variable until the queue is not empty.
   *
   * @param value Reference where the popped value will be stored.
   */
  void WaitAndPop(T& value);

  /**
   * @brief Checks if the queue is empty.
   *
   * @return true If the queue is empty.
   * @return false If the queue is not empty.
   */
  bool Empty() const;

 private:
  std::queue<T> queue_;
  mutable std::mutex mutex_;
  std::condition_variable cond_;
};
