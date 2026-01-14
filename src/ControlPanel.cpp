#include "ControlPanel.h"
#include "VirtualJoystick.h"
#include "ECUConnector.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGroupBox>
#include <QLabel>
#include <QDebug>

ControlPanel::ControlPanel(ECUConnector* connector, QWidget *parent)
    : QWidget(parent), connector_(connector), currentSpeeds_(4, 0) {
    SetupUi();
    
    connect(connector_, &ECUConnector::ConnectionChanged, this, &ControlPanel::OnConnectionChanged);
    
    updateTimer_ = new QTimer(this);
    connect(updateTimer_, &QTimer::timeout, this, &ControlPanel::OnTimerTimeout);
    // Don't start timer immediately, wait for connection
}

void ControlPanel::SetupUi() {
    QHBoxLayout* mainLayout = new QHBoxLayout(this);
    
    // Connection Group
    QGroupBox* connGroup = new QGroupBox("Connection");
    QVBoxLayout* connLayout = new QVBoxLayout(connGroup);
    
    QHBoxLayout* portLayout = new QHBoxLayout();
    portLayout->addWidget(new QLabel("Port:"));
    portEdit_ = new QLineEdit("/dev/ttyUSB0");
    portLayout->addWidget(portEdit_);
    connLayout->addLayout(portLayout);
    
    QHBoxLayout* baudLayout = new QHBoxLayout();
    baudLayout->addWidget(new QLabel("Baud:"));
    baudCombo_ = new QComboBox();
    baudCombo_->addItems({"9600", "115200", "1000000"});
    baudCombo_->setCurrentText("115200");
    baudLayout->addWidget(baudCombo_);
    connLayout->addLayout(baudLayout);
    
    QHBoxLayout* periodLayout = new QHBoxLayout();
    periodLayout->addWidget(new QLabel("Period (ms):"));
    periodSpin_ = new QSpinBox();
    periodSpin_->setRange(10, 1000);
    periodSpin_->setValue(100);
    periodSpin_->setSingleStep(10);
    connect(periodSpin_, QOverload<int>::of(&QSpinBox::valueChanged), this, &ControlPanel::OnPeriodChanged);
    periodLayout->addWidget(periodSpin_);
    connLayout->addLayout(periodLayout);
    
    QHBoxLayout* maxRpmLayout = new QHBoxLayout();
    maxRpmLayout->addWidget(new QLabel("Max RPM:"));
    maxRpmSpin_ = new QSpinBox();
    maxRpmSpin_->setRange(1, 10000);
    maxRpmSpin_->setValue(200);
    connect(maxRpmSpin_, QOverload<int>::of(&QSpinBox::valueChanged), this, &ControlPanel::OnMaxRpmChanged);
    maxRpmLayout->addWidget(maxRpmSpin_);
    connLayout->addLayout(maxRpmLayout);
    
    connectButton_ = new QPushButton("Connect");
    connect(connectButton_, &QPushButton::clicked, this, &ControlPanel::OnConnectClicked);
    connLayout->addWidget(connectButton_);
    connLayout->addStretch();
    
    mainLayout->addWidget(connGroup);
    
    // Sliders Group
    QGroupBox* slidersGroup = new QGroupBox("Motor Control");
    QVBoxLayout* slidersLayout = new QVBoxLayout(slidersGroup);
    
    // All Motors
    QHBoxLayout* allLayout = new QHBoxLayout();
    allLayout->addWidget(new QLabel("All:"));
    allMotorsSlider_ = new QSlider(Qt::Horizontal);
    allMotorsSlider_->setRange(-100, 100);
    allLayout->addWidget(allMotorsSlider_);
    allMotorsSpin_ = new QSpinBox();
    allMotorsSpin_->setRange(-100, 100);
    allLayout->addWidget(allMotorsSpin_);
    slidersLayout->addLayout(allLayout);
    
    connect(allMotorsSlider_, &QSlider::valueChanged, allMotorsSpin_, &QSpinBox::setValue);
    connect(allMotorsSpin_, QOverload<int>::of(&QSpinBox::valueChanged), allMotorsSlider_, &QSlider::setValue);
    connect(allMotorsSlider_, &QSlider::valueChanged, this, &ControlPanel::OnAllMotorsSliderChanged);
    
    allSameCheck_ = new QCheckBox("All Same");
    allSameCheck_->setChecked(true);
    slidersLayout->addWidget(allSameCheck_);
    
    // Individual Motors
    for (int i = 0; i < 4; ++i) {
        QHBoxLayout* motorLayout = new QHBoxLayout();
        motorLayout->addWidget(new QLabel(QString("M%1:").arg(i+1)));
        
        QSlider* slider = new QSlider(Qt::Horizontal);
        slider->setRange(-100, 100);
        motorLayout->addWidget(slider);
        
        QSpinBox* spin = new QSpinBox();
        spin->setRange(-100, 100);
        motorLayout->addWidget(spin);
        
        connect(slider, &QSlider::valueChanged, spin, &QSpinBox::setValue);
        connect(spin, QOverload<int>::of(&QSpinBox::valueChanged), slider, &QSlider::setValue);
        connect(slider, &QSlider::valueChanged, this, [this, i](int val){
            if (!allSameCheck_->isChecked()) {
                currentSpeeds_[i] = val;
            }
        });
        
        motorSliders_.push_back(slider);
        motorSpins_.push_back(spin);
        slidersLayout->addLayout(motorLayout);
    }
    
    QPushButton* stopButton = new QPushButton("STOP ALL");
    stopButton->setStyleSheet("background-color: red; color: white; font-weight: bold;");
    connect(stopButton, &QPushButton::clicked, this, &ControlPanel::OnStopClicked);
    slidersLayout->addWidget(stopButton);
    
    mainLayout->addWidget(slidersGroup);
    
    // Gamepad Group
    QGroupBox* gamepadGroup = new QGroupBox("Gamepad/Joystick Control");
    QVBoxLayout* gamepadLayout = new QVBoxLayout(gamepadGroup);
    
    joystick_ = new VirtualJoystick();
    connect(joystick_, &VirtualJoystick::positionChanged, this, &ControlPanel::OnJoystickPositionChanged);
    gamepadLayout->addWidget(joystick_);
    
    mainLayout->addWidget(gamepadGroup);
    
    // Initialize ranges
    OnMaxRpmChanged(maxRpmSpin_->value());
}

void ControlPanel::OnConnectClicked() {
    if (connector_->IsConnected()) {
        connector_->Disconnect();
    } else {
        connector_->Connect(portEdit_->text(), baudCombo_->currentText().toInt());
    }
}

void ControlPanel::OnConnectionChanged(bool connected) {
    connectButton_->setText(connected ? "Disconnect" : "Connect");
    portEdit_->setEnabled(!connected);
    baudCombo_->setEnabled(!connected);
    
    if (connected) {
        updateTimer_->start(periodSpin_->value());
    } else {
        updateTimer_->stop();
    }
}

void ControlPanel::OnPeriodChanged(int val) {
    if (updateTimer_->isActive()) {
        updateTimer_->setInterval(val);
    }
}

void ControlPanel::OnAllMotorsSliderChanged(int value) {
    if (allSameCheck_->isChecked()) {
        for (auto* slider : motorSliders_) {
            slider->blockSignals(true);
            slider->setValue(value);
            slider->blockSignals(false);
        }
        for (int i = 0; i < 4; ++i) {
            currentSpeeds_[i] = value;
        }
    }
}

void ControlPanel::OnIndividualMotorSliderChanged(int value) {
    // Handled by lambda in SetupUi
}

void ControlPanel::OnTimerTimeout() {
    if (connector_->IsConnected()) {
        connector_->SetAllMotorsSpeed(currentSpeeds_);
        connector_->GetAllEncoders();
        connector_->GetImu();
    }
}

void ControlPanel::OnStopClicked() {
    allMotorsSlider_->setValue(0);
    for (auto* slider : motorSliders_) {
        slider->setValue(0);
    }
    std::fill(currentSpeeds_.begin(), currentSpeeds_.end(), 0);
    if (connector_->IsConnected()) {
        connector_->SetAllMotorsSpeed(currentSpeeds_);
    }
}

int ControlPanel::GetMaxRpm() const {
    return maxRpmSpin_ ? maxRpmSpin_->value() : 200;
}

void ControlPanel::OnMaxRpmChanged(int value) {
    if (allMotorsSlider_) allMotorsSlider_->setRange(-value, value);
    if (allMotorsSpin_) allMotorsSpin_->setRange(-value, value);
    
    for (auto* slider : motorSliders_) {
        if (slider) slider->setRange(-value, value);
    }
    for (auto* spin : motorSpins_) {
        if (spin) spin->setRange(-value, value);
    }
    
    emit MaxRpmChanged(value);
}

void ControlPanel::OnJoystickPositionChanged(double x, double y) {
    // Differential drive: y = forward/back, x = turn
    // Left motors (M1, M2): -y + x, Right motors (M3, M4): -y - x
    // (negate y because up on joystick should be forward)
    int maxRpm = maxRpmSpin_->value();
    int leftSpeed = static_cast<int>((-y + x) * maxRpm);
    int rightSpeed = static_cast<int>((-y - x) * maxRpm);
    
    // Clamp to range
    leftSpeed = qBound(-maxRpm, leftSpeed, maxRpm);
    rightSpeed = qBound(-maxRpm, rightSpeed, maxRpm);
    
    // Motors: M1,M2 = left side, M3,M4 = right side
    currentSpeeds_[0] = leftSpeed;  // M1
    currentSpeeds_[1] = leftSpeed;  // M2
    currentSpeeds_[2] = rightSpeed; // M3
    currentSpeeds_[3] = rightSpeed; // M4
    
    // Update sliders to reflect
    allSameCheck_->setChecked(false); // Individual mode
    for (int i = 0; i < 4; ++i) {
        motorSliders_[i]->blockSignals(true);
        motorSliders_[i]->setValue(currentSpeeds_[i]);
        motorSliders_[i]->blockSignals(false);
    }
    
    // Motor speeds will be sent by the periodic timer
}

void ControlPanel::SetPeriodicUpdatesEnabled(bool enabled) {
    if (enabled) {
        if (connector_->IsConnected()) {
            updateTimer_->start(periodSpin_->value());
        }
    } else {
        updateTimer_->stop();
    }
}
