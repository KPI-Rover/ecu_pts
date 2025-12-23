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

private slots:
    void OnCommandChanged(int index);
    void OnSendClicked();
    void OnLogMessage(const QString& msg);

private:
    void SetupUi();

    ECUConnector* connector_;
    
    QComboBox* cmdCombo_;
    QStackedWidget* paramsStack_;
    QTextEdit* logText_;
    QPushButton* sendButton_;
    
    // Params for SetMotorSpeed
    QSpinBox* motorIdSpin_;
    QSpinBox* speedSpin_;
    
    // Params for SetAllMotorsSpeed
    QSpinBox* allSpeedsSpins_[4];
};
