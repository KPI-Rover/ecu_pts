#include "ProtocolTestPanel.h"
#include "ECUConnector.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGroupBox>
#include <QLabel>
#include <QDateTime>

ProtocolTestPanel::ProtocolTestPanel(ECUConnector* connector, QWidget *parent)
    : QWidget(parent), connector_(connector), loggingEnabled_(false) {
    SetupUi();
    
    connect(connector_, &ECUConnector::ApiVersionReceived, this, [this](int version){
        OnLogMessage(QString("RX <- get_api_version response: API version = %1").arg(version));
    });
    
    connect(connector_, &ECUConnector::EncoderValuesUpdated, this, [this](const std::vector<float>& values){
        QStringList strValues;
        for(float v : values) strValues << QString::number(v);
        OnLogMessage(QString("RX <- get_all_encoders response: [%1]").arg(strValues.join(", ")));
    });
    
    connect(connector_, &ECUConnector::EncoderValueUpdated, this, [this](int motorId, float value){
        OnLogMessage(QString("RX <- get_encoder response: Motor %1 = %2").arg(motorId).arg(value));
    });
    
    connect(connector_, &ECUConnector::ImuDataReceived, this, [this](const ImuData& data){
        QString msg = QString("RX <- get_imu response:\n"
                              "  Accel: x=%1, y=%2, z=%3\n"
                              "  Gyro:  x=%4, y=%5, z=%6\n"
                              "  Mag:   x=%7, y=%8, z=%9\n"
                              "  Quat:  w=%10, x=%11, y=%12, z=%13")
                      .arg(data.accel_x).arg(data.accel_y).arg(data.accel_z)
                      .arg(data.gyro_x).arg(data.gyro_y).arg(data.gyro_z)
                      .arg(data.mag_x).arg(data.mag_y).arg(data.mag_z)
                      .arg(data.quat_w).arg(data.quat_x).arg(data.quat_y).arg(data.quat_z);
        OnLogMessage(msg);
    });

    connect(connector_, &ECUConnector::RawDataSent, this, &ProtocolTestPanel::OnRawDataSent);
    connect(connector_, &ECUConnector::RawDataReceived, this, &ProtocolTestPanel::OnRawDataReceived);
}

void ProtocolTestPanel::SetupUi() {
    QVBoxLayout* mainLayout = new QVBoxLayout(this);
    
    // Command Selection
    QGroupBox* inputGroup = new QGroupBox("Command Selection");
    QVBoxLayout* inputLayout = new QVBoxLayout(inputGroup);
    
    QHBoxLayout* cmdLayout = new QHBoxLayout();
    cmdLayout->addWidget(new QLabel("Command:"));
    cmdCombo_ = new QComboBox();
    cmdCombo_->addItems({
        "get_api_version (0x01)",
        "set_motor_speed (0x02)",
        "set_all_motors_speed (0x03)",
        "get_encoder (0x04)", // Not implemented in Connector yet
        "get_all_encoders (0x05)",
        "get_imu (0x06)"
    });
    connect(cmdCombo_, QOverload<int>::of(&QComboBox::currentIndexChanged), this, &ProtocolTestPanel::OnCommandChanged);
    cmdLayout->addWidget(cmdCombo_);
    inputLayout->addLayout(cmdLayout);
    
    paramsStack_ = new QStackedWidget();
    
    // 0: get_api_version
    paramsStack_->addWidget(new QWidget());
    
    // 1: set_motor_speed
    QWidget* pageSetSpeed = new QWidget();
    QHBoxLayout* layoutSetSpeed = new QHBoxLayout(pageSetSpeed);
    layoutSetSpeed->addWidget(new QLabel("Motor ID:"));
    motorIdSpin_ = new QSpinBox();
    motorIdSpin_->setRange(0, 3);
    layoutSetSpeed->addWidget(motorIdSpin_);
    layoutSetSpeed->addWidget(new QLabel("Speed:"));
    speedSpin_ = new QSpinBox();
    speedSpin_->setRange(-100, 100);
    layoutSetSpeed->addWidget(speedSpin_);
    layoutSetSpeed->addStretch();
    paramsStack_->addWidget(pageSetSpeed);
    
    // 2: set_all_motors_speed
    QWidget* pageSetAll = new QWidget();
    QHBoxLayout* layoutSetAll = new QHBoxLayout(pageSetAll);
    for (int i = 0; i < 4; ++i) {
        layoutSetAll->addWidget(new QLabel(QString("M%1:").arg(i)));
        allSpeedsSpins_[i] = new QSpinBox();
        allSpeedsSpins_[i]->setRange(-100, 100);
        layoutSetAll->addWidget(allSpeedsSpins_[i]);
    }
    layoutSetAll->addStretch();
    paramsStack_->addWidget(pageSetAll);
    
    // 3: get_encoder
    QWidget* pageGetEncoder = new QWidget();
    QHBoxLayout* layoutGetEncoder = new QHBoxLayout(pageGetEncoder);
    layoutGetEncoder->addWidget(new QLabel("Motor ID:"));
    encoderMotorIdSpin_ = new QSpinBox();
    encoderMotorIdSpin_->setRange(0, 3);
    layoutGetEncoder->addWidget(encoderMotorIdSpin_);
    layoutGetEncoder->addStretch();
    paramsStack_->addWidget(pageGetEncoder);
    
    // 4: get_all_encoders
    paramsStack_->addWidget(new QWidget());
    
    // 5: get_imu
    paramsStack_->addWidget(new QWidget());
    
    inputLayout->addWidget(paramsStack_);
    
    sendButton_ = new QPushButton("Send Command");
    connect(sendButton_, &QPushButton::clicked, this, &ProtocolTestPanel::OnSendClicked);
    inputLayout->addWidget(sendButton_);
    
    mainLayout->addWidget(inputGroup);
    
    // Log Area
    QGroupBox* logGroup = new QGroupBox("Log");
    QVBoxLayout* logLayout = new QVBoxLayout(logGroup);
    logText_ = new QTextEdit();
    logText_->setReadOnly(true);
    logLayout->addWidget(logText_);
    mainLayout->addWidget(logGroup);
}

void ProtocolTestPanel::OnCommandChanged(int index) {
    paramsStack_->setCurrentIndex(index);
}

void ProtocolTestPanel::OnSendClicked() {
    if (!connector_->IsConnected()) {
        OnLogMessage("Error: Not connected");
        return;
    }
    
    int index = cmdCombo_->currentIndex();
    switch (index) {
        case 0: // get_api_version
            OnLogMessage("TX -> get_api_version (0x01)");
            connector_->GetApiVersion();
            break;
        case 1: // set_motor_speed
            OnLogMessage(QString("TX -> set_motor_speed (0x02) ID=%1 Speed=%2").arg(motorIdSpin_->value()).arg(speedSpin_->value()));
            connector_->SetMotorSpeed(motorIdSpin_->value(), speedSpin_->value());
            break;
        case 2: // set_all_motors_speed
        {
            std::vector<int> speeds;
            QStringList strSpeeds;
            for (int i = 0; i < 4; ++i) {
                speeds.push_back(allSpeedsSpins_[i]->value());
                strSpeeds << QString::number(speeds.back());
            }
            OnLogMessage(QString("TX -> set_all_motors_speed (0x03) [%1]").arg(strSpeeds.join(", ")));
            connector_->SetAllMotorsSpeed(speeds);
            break;
        }
        case 3: // get_encoder
            OnLogMessage(QString("TX -> get_encoder (0x04) ID=%1").arg(encoderMotorIdSpin_->value()));
            connector_->GetEncoder(encoderMotorIdSpin_->value());
            break;
        case 4: // get_all_encoders
            OnLogMessage("TX -> get_all_encoders (0x05)");
            connector_->GetAllEncoders();
            break;
        case 5: // get_imu
            OnLogMessage("TX -> get_imu (0x06)");
            connector_->GetImu();
            break;
    }
}

void ProtocolTestPanel::OnLogMessage(const QString& msg) {
    if (!loggingEnabled_) return;
    
    QString timestamp = QDateTime::currentDateTime().toString("HH:mm:ss.zzz");
    logText_->append(QString("[%1] %2").arg(timestamp, msg));
}

void ProtocolTestPanel::SetLoggingEnabled(bool enabled) {
    loggingEnabled_ = enabled;
}

void ProtocolTestPanel::OnRawDataSent(const std::vector<uint8_t>& data) {
    if (!loggingEnabled_) return;
    QString hex;
    for (uint8_t b : data) hex += QString("%1 ").arg(b, 2, 16, QChar('0')).toUpper();
    OnLogMessage(QString("TX RAW: [ %1]").arg(hex));
}

void ProtocolTestPanel::OnRawDataReceived(const std::vector<uint8_t>& data) {
    if (!loggingEnabled_) return;
    QString hex;
    for (uint8_t b : data) hex += QString("%1 ").arg(b, 2, 16, QChar('0')).toUpper();
    OnLogMessage(QString("RX RAW: [ %1]").arg(hex));
}
