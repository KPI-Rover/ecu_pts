#include "DashboardPanel.h"
#include "ECUConnector.h"
#include "ProtocolTestPanel.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGroupBox>
#include <QLabel>
#include <QDateTime>
#include <QDebug>

DashboardPanel::DashboardPanel(ECUConnector* connector, QWidget *parent)
    : QWidget(parent), connector_(connector), lastEncoders_(4, 0), startTime_(0) {
    SetupUi();
    SetupChart();
    
    connect(connector_, &ECUConnector::EncoderValuesUpdated, this, &DashboardPanel::OnEncoderDataReceived);
    connect(connector_, &ECUConnector::SpeedSet, this, [this](const std::vector<int>& speeds){
        // Update setpoint series
        // We need to sync this with the timer or just add a point at current time
        // For simplicity, we'll just store it and use it when updating the chart or update immediately
        // But chart X axis is time.
        // Let's just update the setpoint value for the next plot update?
        // Or better, add a point now.
        qint64 now = QDateTime::currentMSecsSinceEpoch();
        if (startTime_ == 0) startTime_ = now;
        qreal t = (now - startTime_);
        
        for (int i = 0; i < 4; ++i) {
            if (i < speeds.size()) {
                setpointSeries_[i]->append(t, speeds[i]);
                if (setpointSeries_[i]->count() > 1000) setpointSeries_[i]->remove(0);
            }
        }
    });
}

void DashboardPanel::SetupUi() {
    QVBoxLayout* mainLayout = new QVBoxLayout(this);
    mainLayout->setContentsMargins(0, 0, 0, 0);
    
    tabWidget_ = new QTabWidget();
    mainLayout->addWidget(tabWidget_);
    
    // Chart Tab
    chartTab_ = new QWidget();
    QVBoxLayout* chartLayout = new QVBoxLayout(chartTab_);
    
    // Controls
    QGroupBox* controlsGroup = new QGroupBox("Chart Controls");
    QHBoxLayout* controlsLayout = new QHBoxLayout(controlsGroup);
    
    for (int i = 0; i < 4; ++i) {
        motorChecks_[i] = new QCheckBox(QString("Motor %1").arg(i+1));
        motorChecks_[i]->setChecked(true);
        connect(motorChecks_[i], &QCheckBox::stateChanged, this, &DashboardPanel::OnMotorSelectionChanged);
        controlsLayout->addWidget(motorChecks_[i]);
    }
    
    controlsLayout->addStretch();
    
    autoScrollCheck_ = new QCheckBox("Auto-scroll");
    autoScrollCheck_->setChecked(true);
    connect(autoScrollCheck_, &QCheckBox::stateChanged, this, &DashboardPanel::OnAutoScrollChanged);
    controlsLayout->addWidget(autoScrollCheck_);
    
    controlsLayout->addWidget(new QLabel("Encoder Ticks/Rev:"));
    ticksSpin_ = new QSpinBox();
    ticksSpin_->setRange(1, 10000);
    ticksSpin_->setValue(TICKS_PER_REV_DEFAULT);
    ticksSpin_->setToolTip("Encoder ticks per revolution (applies to all motors)");
    connect(ticksSpin_, QOverload<int>::of(&QSpinBox::valueChanged), this, &DashboardPanel::OnTicksChanged);
    controlsLayout->addWidget(ticksSpin_);
    
    chartLayout->addWidget(controlsGroup);
    
    // Chart View
    chartView_ = new QChartView();
    chartView_->setRenderHint(QPainter::Antialiasing);
    chartLayout->addWidget(chartView_);
    
    tabWidget_->addTab(chartTab_, "PID Regulator");
    
    // Protocol Test Tab
    protocolTab_ = new ProtocolTestPanel(connector_);
    tabWidget_->addTab(protocolTab_, "Protocol Tester");
}

void DashboardPanel::SetupChart() {
    chart_ = new QChart();
    chart_->setTitle("Motor Speed Control - Setpoint vs Actual RPM");
    
    axisX_ = new QValueAxis();
    axisX_->setTitleText("Time (ms)");
    axisX_->setRange(0, 10000);
    chart_->addAxis(axisX_, Qt::AlignBottom);
    
    axisY_ = new QValueAxis();
    axisY_->setTitleText("RPM");
    axisY_->setRange(-100, 100);
    chart_->addAxis(axisY_, Qt::AlignLeft);
    
    QColor colors[] = {Qt::red, Qt::blue, Qt::green, QColor("orange")};
    
    for (int i = 0; i < 4; ++i) {
        // Setpoint
        setpointSeries_[i] = new QLineSeries();
        setpointSeries_[i]->setName(QString("Motor %1 Setpoint").arg(i+1));
        QPen pen(colors[i]);
        pen.setStyle(Qt::DotLine);
        pen.setWidth(2);
        setpointSeries_[i]->setPen(pen);
        chart_->addSeries(setpointSeries_[i]);
        setpointSeries_[i]->attachAxis(axisX_);
        setpointSeries_[i]->attachAxis(axisY_);
        
        // Current
        currentSeries_[i] = new QLineSeries();
        currentSeries_[i]->setName(QString("Motor %1 RPM").arg(i+1));
        QPen penSolid(colors[i]);
        penSolid.setWidth(2);
        currentSeries_[i]->setPen(penSolid);
        chart_->addSeries(currentSeries_[i]);
        currentSeries_[i]->attachAxis(axisX_);
        currentSeries_[i]->attachAxis(axisY_);
    }
    
    chartView_->setChart(chart_);
}

void DashboardPanel::OnEncoderDataReceived(const std::vector<float>& encoders) {
    qint64 now = QDateTime::currentMSecsSinceEpoch();
    if (startTime_ == 0) startTime_ = now;
    
    qreal t = (now - startTime_);
    
    for (int i = 0; i < 4; ++i) {
        if (i >= encoders.size()) break;
        
        float currentEncoder = encoders[i];
        
        // Accumulate ticks (currentEncoder is delta)
        motorData_[i].accumulatedTicks += currentEncoder;
        
        // Calculate RPM only if enough time passed (e.g. > 10ms) to avoid division by small numbers
        // or bursty updates causing 0 RPM
        if (motorData_[i].lastTime == 0) {
            motorData_[i].lastTime = now;
            // Don't plot yet
            continue;
        }

        qint64 dt = now - motorData_[i].lastTime;
        
        // If we have a burst of packets, dt might be 0. Accumulate ticks and wait.
        if (dt >= 20) { 
            float dTicks = motorData_[i].accumulatedTicks;
            float rpm = (dTicks / ticksSpin_->value()) * (60000.0f / dt);
            
            motorData_[i].accumulatedTicks = 0;
            motorData_[i].lastTime = now;
            
            currentSeries_[i]->append(t, rpm);
            if (currentSeries_[i]->count() > 1000) currentSeries_[i]->remove(0);
        }
        
        // Also add a point for setpoint to keep lines in sync visually
        // Ideally we should interpolate or hold last value
        std::vector<int> speeds = connector_->GetCurrentSpeeds();
        if (i < speeds.size()) {
             // Only add setpoint point if we added a current point? 
             // Or always? If we don't add current point, chart might lag?
             // Let's add setpoint point only when we update RPM to keep X axis synced
             if (dt >= 20) {
                 setpointSeries_[i]->append(t, speeds[i]);
                 if (setpointSeries_[i]->count() > 1000) setpointSeries_[i]->remove(0);
             }
        }
    }
    
    if (autoScrollCheck_->isChecked()) {
        if (t > 10000) {
            axisX_->setRange(t - 10000, t);
        }
    }
}

void DashboardPanel::OnMotorSelectionChanged() {
    for (int i = 0; i < 4; ++i) {
        bool visible = motorChecks_[i]->isChecked();
        setpointSeries_[i]->setVisible(visible);
        currentSeries_[i]->setVisible(visible);
    }
}

void DashboardPanel::OnAutoScrollChanged(int state) {
    if (state == Qt::Checked) {
        chart_->setAnimationOptions(QChart::NoAnimation); // Performance
    } else {
        // Enable zoom/scroll?
    }
}

void DashboardPanel::OnTicksChanged(int val) {
    // Just updates the value used in calculation
}

void DashboardPanel::SetMaxRpm(int value) {
    if (axisY_) {
        axisY_->setRange(-value, value);
    }
}
