#pragma once

#include <QWidget>
#include <QComboBox>
#include <QStackedWidget>
#include <QSpinBox>
#include <QTextEdit>
#include <QPushButton>

class ECUConnector;

class ProtocolTestPanel : public QWidget {
    Q_OBJECT

public:
    explicit ProtocolTestPanel(ECUConnector* connector, QWidget *parent = nullptr);
    
    void SetLoggingEnabled(bool enabled);

private slots:
    void OnCommandChanged(int index);
    void OnSendClicked();
    void OnLogMessage(const QString& msg);
    void OnRawDataSent(const std::vector<uint8_t>& data);
    void OnRawDataReceived(const std::vector<uint8_t>& data);

private:
    void SetupUi();

    ECUConnector* connector_;
    bool loggingEnabled_;
    
    QComboBox* cmdCombo_;
    QStackedWidget* paramsStack_;
    QTextEdit* logText_;
    QPushButton* sendButton_;
    
    // Params for SetMotorSpeed
    QSpinBox* motorIdSpin_;
    QSpinBox* speedSpin_;
    
    // Params for GetEncoder
    QSpinBox* encoderMotorIdSpin_;
    
    // Params for SetAllMotorsSpeed
    QSpinBox* allSpeedsSpins_[4];
};
