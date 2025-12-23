#include "ECUConnector.h"
#include <QDebug>

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

void ECUConnector::GetApiVersion() {
    if (!IsConnected()) return;
    // Command ID 0x01, ROS2 Driver Version (1)
    std::vector<uint8_t> data;
    data.push_back(0x01);
    data.push_back(0x01);
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
        }
        // Handle other responses if needed
    }
}
