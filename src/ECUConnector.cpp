#include "ECUConnector.h"
#include <QDebug>
#include <cstring>

ECUConnector::ECUConnector(QObject *parent) : QObject(parent) {
    pollTimer_ = new QTimer(this);
    connect(pollTimer_, &QTimer::timeout, this, &ECUConnector::ProcessIncomingData);
}

ECUConnector::~ECUConnector() {
    Disconnect();
}

void ECUConnector::Connect(const QString &port, int baud) {
    try {
        transport_ = std::make_unique<SerialTransport>(port.toStdString(), baud);
        transport_->SetLogCallback([this](const std::vector<uint8_t>& data, bool isTx) {
            if (isTx) {
                emit RawDataSent(data);
            } else {
                emit RawDataReceived(data);
            }
        });
        transport_->Start();
        pollTimer_->start(10); // Poll every 10ms
        emit ConnectionChanged(true);
    } catch (const std::exception &e) {
        emit ErrorOccurred(QString::fromStdString(e.what()));
        emit ConnectionChanged(false);
    }
}

void ECUConnector::Disconnect() {
    if (transport_) {
        transport_->Stop();
        transport_.reset();
    }
    pollTimer_->stop();
    emit ConnectionChanged(false);
}

bool ECUConnector::IsConnected() const {
    return transport_ && transport_->IsConnected();
}

void ECUConnector::SetMotorSpeed(int motorId, int speed) {
    if (!IsConnected() || motorId < 0 || motorId > 3) return;
    
    currentSpeeds_[motorId] = speed;
    emit SpeedSet(currentSpeeds_);

    // Command ID 0x02, MotorID, Speed (4 bytes)
    std::vector<uint8_t> data;
    data.push_back(0x02);
    data.push_back(static_cast<uint8_t>(motorId));
    
    int32_t speedVal = speed * 100;
    data.push_back((speedVal >> 24) & 0xFF);
    data.push_back((speedVal >> 16) & 0xFF);
    data.push_back((speedVal >> 8) & 0xFF);
    data.push_back(speedVal & 0xFF);
    
    transport_->Send(data);
}

void ECUConnector::SetAllMotorsSpeed(const std::vector<int>& speeds) {
    if (!IsConnected() || speeds.size() != 4) return;
    
    currentSpeeds_ = speeds;
    emit SpeedSet(currentSpeeds_);

    // Command ID 0x03, Speed1, Speed2, Speed3, Speed4
    std::vector<uint8_t> data;
    data.push_back(0x03);
    
    for (int speed : speeds) {
        int32_t speedVal = speed * 100;
        data.push_back((speedVal >> 24) & 0xFF);
        data.push_back((speedVal >> 16) & 0xFF);
        data.push_back((speedVal >> 8) & 0xFF);
        data.push_back(speedVal & 0xFF);
    }
    
    transport_->Send(data);
}

void ECUConnector::GetAllEncoders() {
    if (!IsConnected()) return;
    // Command ID 0x05
    std::vector<uint8_t> data;
    data.push_back(0x05);
    transport_->Send(data);
}

void ECUConnector::GetEncoder(int motorId) {
    if (!IsConnected() || motorId < 0 || motorId > 3) return;
    lastRequestedEncoderMotor_ = motorId;
    // Command ID 0x04, MotorID
    std::vector<uint8_t> data;
    data.push_back(0x04);
    data.push_back(static_cast<uint8_t>(motorId));
    transport_->Send(data);
}

void ECUConnector::GetApiVersion() {
    if (!IsConnected()) return;
    // Command ID 0x01, ROS2 Driver Version (1)
    std::vector<uint8_t> data;
    data.push_back(0x01);
    data.push_back(0x01);
    transport_->Send(data);
}

void ECUConnector::GetImu() {
    if (!IsConnected()) return;
    // Command ID 0x06
    std::vector<uint8_t> data;
    data.push_back(0x06);
    transport_->Send(data);
}

void ECUConnector::ProcessIncomingData() {
    if (!transport_) return;
    
    std::vector<uint8_t> payload;
    while (transport_->Read(payload)) {
        if (payload.empty()) continue;
        
        uint8_t cmdId = payload[0];
        if (cmdId == 0x01) { // GetApiVersion response
            if (payload.size() >= 2) {
                int version = payload[1];
                emit ApiVersionReceived(version);
            }
        } else if (cmdId == 0x04) { // GetEncoder response
            // Payload: CmdID (1) + EncoderValue (4 bytes)
            if (payload.size() >= 5 && lastRequestedEncoderMotor_ >= 0) {
                int32_t val = (payload[1] << 24) | (payload[2] << 16) | 
                              (payload[3] << 8) | payload[4];
                emit EncoderValueUpdated(lastRequestedEncoderMotor_, static_cast<float>(val));
                lastRequestedEncoderMotor_ = -1; // Reset
            }
        } else if (cmdId == 0x05) { // GetAllEncoders response
            // Payload: CmdID (1) + 4 * 4 bytes
            if (payload.size() >= 17) {
                std::vector<float> values;
                for (int i = 0; i < 4; ++i) {
                    int offset = 1 + i * 4;
                    int32_t val = (payload[offset] << 24) | (payload[offset+1] << 16) | 
                                  (payload[offset+2] << 8) | payload[offset+3];
                    values.push_back(static_cast<float>(val));
                }
                emit EncoderValuesUpdated(values);
            }
        } else if (cmdId == 0x06) { // GetImu response
            // Payload: CmdID (1) + 13 floats (4 bytes each) = 53 bytes
            if (payload.size() >= 53) {
                ImuData data;
                auto readFloat = [&](int offset) {
                    uint32_t val = (static_cast<uint32_t>(payload[offset+3]) << 24) |
                                   (static_cast<uint32_t>(payload[offset+2]) << 16) |
                                   (static_cast<uint32_t>(payload[offset+1]) << 8) |
                                   (static_cast<uint32_t>(payload[offset]));
                    float f;
                    std::memcpy(&f, &val, 4);
                    return f;
                };

                data.accel_x = readFloat(5); // Swapped: mapping hardware Y to application X
                data.accel_y = readFloat(1); // Swapped: mapping hardware X to application Y
                data.accel_z = readFloat(9);
                data.gyro_x = readFloat(17); // Swapped
                data.gyro_y = readFloat(13); // Swapped
                data.gyro_z = readFloat(21);
                data.mag_x = readFloat(29);  // Swapped
                data.mag_y = readFloat(25);  // Swapped
                data.mag_z = readFloat(33);
                data.quat_w = readFloat(37);
                data.quat_x = readFloat(41); // Native X
                data.quat_y = readFloat(45); // Native Y
                data.quat_z = readFloat(49);
                
                emit ImuDataReceived(data);
            }
        }
        // Handle other responses if needed
    }
}
