#include <atomic>
#include <chrono>
#include <csignal>
#include <iomanip>
#include <iostream>

#include "SerialTransport.h"

std::atomic<bool> running(true);

void SignalHandler(int signum) { running = false; }

int main(int argc, char* argv[]) {
  if (argc < 3) {
    std::cerr << "Usage: " << argv[0] << " <port> <baudrate>" << std::endl;
    return 1;
  }

  signal(SIGINT, SignalHandler);

  try {
    SerialTransport transport(argv[1], std::stoi(argv[2]));
    transport.Start();

    std::cout << "SerialTransport started. Waiting for frames..." << std::endl;

    uint32_t last_counter = 0;
    uint64_t lost_packets = 0;
    bool first_packet = true;
    auto last_print_time = std::chrono::steady_clock::now();

    while (running) {
      std::vector<uint8_t> payload;
      if (transport.Read(payload)) {
        // Payload: [BE] [DA] [Counter...]
        if (payload.size() >= 6 && payload[0] == 0xBE && payload[1] == 0xDA) {
          uint32_t current_counter = (payload[2] << 24) | (payload[3] << 16) |
                                     (payload[4] << 8) | payload[5];

          if (!first_packet) {
            if (current_counter > last_counter + 1) {
              lost_packets += (current_counter - last_counter - 1);
            }
          } else {
            first_packet = false;
          }
          last_counter = current_counter;
        }

        auto now = std::chrono::steady_clock::now();
        if (std::chrono::duration_cast<std::chrono::milliseconds>(
                now - last_print_time)
                .count() > 100) {
          std::cout << "\rCnt: " << last_counter << " | Lost: " << lost_packets
                    << "   " << std::flush;
          last_print_time = now;
        }
      } else {
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
      }
    }

    transport.Stop();

  } catch (const std::exception& e) {
    std::cerr << e.what() << std::endl;
    return 1;
  }
  return 0;
}
