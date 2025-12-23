#include "ProtocolTestPanel.h"
#include "ECUConnector.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGroupBox>
#include <QLabel>
#include <QDateTime>

ProtocolTestPanel::ProtocolTestPanel(ECUConnector* connector, QWidget *parent)
    : QWidget(parent), connector_(connector) {
    SetupUi();
    
    connect(connector_, &ECUConnector::ApiVersionReceived, this, [this](int version){
        OnLogMessage(QString("RX <- get_api_version response: API version = %1").arg(version));
    });
    
    connect(connector_, &ECUConnector::EncoderValuesUpdated, this, [this](const std::vector<float>& values){
        QStringList strValues;
        for(float v : values) strValues << QString::number(v);
        OnLogMessage(QString("RX <- get_all_encoders response: [%1]").arg(strValues.join(", ")));
    });
    
    // We don't have specific signals for SetMotorSpeed response in ECUConnector yet (it just sends),
    // but we can log the TX.
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
        "get_all_encoders (0x05)"
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
    
    // 3: get_encoder (Placeholder)
    paramsStack_->addWidget(new QWidget());
    
    // 4: get_all_encoders
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
            OnLogMessage("Error: get_encoder (0x04) not implemented");
            break;
        case 4: // get_all_encoders
            OnLogMessage("TX -> get_all_encoders (0x05)");
            connector_->GetAllEncoders();
            break;
    }
}

void ProtocolTestPanel::OnLogMessage(const QString& msg) {
    QString timestamp = QDateTime::currentDateTime().toString("HH:mm:ss.zzz");
    logText_->append(QString("[%1] %2").arg(timestamp, msg));
}
