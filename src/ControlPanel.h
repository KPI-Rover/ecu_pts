#pragma once

#include <QWidget>
#include <QComboBox>
#include <QLineEdit>
#include <QPushButton>
#include <QSlider>
#include <QSpinBox>
#include <QCheckBox>
#include <QTimer>
#include <vector>

class ECUConnector;

class ControlPanel : public QWidget {
    Q_OBJECT
public:
    explicit ControlPanel(ECUConnector* connector, QWidget *parent = nullptr);
    int GetMaxRpm() const;

signals:
    void MaxRpmChanged(int value);

private slots:
    void OnConnectClicked();
    void OnConnectionChanged(bool connected);
    void OnAllMotorsSliderChanged(int value);
    void OnIndividualMotorSliderChanged(int value);
    void OnTimerTimeout();
    void OnStopClicked();
    void OnPeriodChanged(int val);
    void OnMaxRpmChanged(int value);

private:
    void SetupUi();
    
    ECUConnector* connector_;
    
    // Connection UI
    QLineEdit* portEdit_;
    QComboBox* baudCombo_;
    QSpinBox* periodSpin_;
    QSpinBox* maxRpmSpin_;
    QPushButton* connectButton_;
    
    // Sliders UI
    QSlider* allMotorsSlider_;
    QSpinBox* allMotorsSpin_;
    QCheckBox* allSameCheck_;
    std::vector<QSlider*> motorSliders_;
    std::vector<QSpinBox*> motorSpins_;
    
    QTimer* updateTimer_;
    std::vector<int> currentSpeeds_;
};
