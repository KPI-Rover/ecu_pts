#include "ThreadSafeQueue.h"

#include <vector>
#include <cstdint>

template <typename T>
void ThreadSafeQueue<T>::Push(const T& value) {
  std::lock_guard<std::mutex> lock(mutex_);
  queue_.push(value);
  cond_.notify_one();
}

template <typename T>
bool ThreadSafeQueue<T>::Pop(T& value) {
  std::unique_lock<std::mutex> lock(mutex_);
  if (queue_.empty()) {
    return false;
  }
  value = queue_.front();
  queue_.pop();
  return true;
}

template <typename T>
void ThreadSafeQueue<T>::WaitAndPop(T& value) {
  std::unique_lock<std::mutex> lock(mutex_);
  cond_.wait(lock, [this] { return !queue_.empty(); });
  value = queue_.front();
  queue_.pop();
}

template <typename T>
bool ThreadSafeQueue<T>::Empty() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return queue_.empty();
}

// Explicit instantiation for the types used in the application
template class ThreadSafeQueue<std::vector<uint8_t>>;
