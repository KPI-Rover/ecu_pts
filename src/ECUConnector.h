#pragma once

#include <QObject>
#include <QTimer>
#include <memory>
#include <vector>
#include "SerialTransport.h"

struct ImuData {
    float accel_x, accel_y, accel_z;
    float gyro_x, gyro_y, gyro_z;
    float mag_x, mag_y, mag_z;
    float quat_w, quat_x, quat_y, quat_z;
};

class ECUConnector : public QObject {
    Q_OBJECT
public:
    explicit ECUConnector(QObject *parent = nullptr);
    ~ECUConnector();

    void Connect(const QString &port, int baud);
    void Disconnect();
    bool IsConnected() const;

    void SetMotorSpeed(int motorId, int speed);
    void SetAllMotorsSpeed(const std::vector<int>& speeds);
    void GetEncoder(int motorId);
    void GetAllEncoders();
    void GetApiVersion();
    void GetImu();
    
    std::vector<int> GetCurrentSpeeds() const { return currentSpeeds_; }

signals:
    void ConnectionChanged(bool connected);
    void ErrorOccurred(const QString &message);
    void EncoderValuesUpdated(const std::vector<float>& values);
    void EncoderValueUpdated(int motorId, float value);
    void ApiVersionReceived(int version);
    void SpeedSet(const std::vector<int>& speeds);
    void ImuDataReceived(const ImuData& data);
    void RawDataSent(const std::vector<uint8_t>& data);
    void RawDataReceived(const std::vector<uint8_t>& data);

private slots:
    void ProcessIncomingData();

private:
    std::unique_ptr<SerialTransport> transport_;
    QTimer *pollTimer_;
    std::vector<int> currentSpeeds_{0, 0, 0, 0};
    int lastRequestedEncoderMotor_{-1};
};
