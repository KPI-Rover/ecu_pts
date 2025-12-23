#pragma once

#include <QObject>
#include <QTimer>
#include <memory>
#include <vector>
#include "SerialTransport.h"

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
    void GetAllEncoders();
    void GetApiVersion();
    
    std::vector<int> GetCurrentSpeeds() const { return currentSpeeds_; }

signals:
    void ConnectionChanged(bool connected);
    void ErrorOccurred(const QString &message);
    void EncoderValuesUpdated(const std::vector<float>& values);
    void ApiVersionReceived(int version);
    void SpeedSet(const std::vector<int>& speeds);

private slots:
    void ProcessIncomingData();

private:
    std::unique_ptr<SerialTransport> transport_;
    QTimer *pollTimer_;
    std::vector<int> currentSpeeds_{0, 0, 0, 0};
};
