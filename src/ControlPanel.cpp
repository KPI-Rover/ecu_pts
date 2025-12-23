#include "ControlPanel.h"
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
    periodSpin_->setValue(50);
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
    
    mainLayout->addWidget(connGroup, 1);
    
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
    
    mainLayout->addWidget(slidersGroup, 4);
    
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
