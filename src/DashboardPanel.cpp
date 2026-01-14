#include "DashboardPanel.h"
#include "ECUConnector.h"
#include "ProtocolTestPanel.h"
#include "IMUPanel.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGroupBox>
#include <QLabel>
#include <QDateTime>
#include <QDebug>
#include <QWheelEvent>
#include <limits>

ZoomableChartView::ZoomableChartView(QWidget *parent)
    : QChartView(parent) {
}

void ZoomableChartView::wheelEvent(QWheelEvent *event) {
    if (event->modifiers() & Qt::ControlModifier) {
        // Ctrl + wheel: Zoom in/out on X-axis only
        qreal factor = (event->angleDelta().y() > 0) ? 0.8 : 1.25; // Zoom in/out
        
        QRectF rect = chart()->plotArea();
        QPointF center = chart()->mapToValue(event->position(), chart()->series().first());
        
        qreal newWidth = rect.width() * factor;
        qreal left = center.x() - (center.x() - rect.left()) * factor;
        
        chart()->zoomIn(QRectF(left, rect.top(), newWidth, rect.height()));
        emit viewChanged();
        event->accept();
    } else {
        // Mouse wheel: Scroll X-axis horizontally
        qreal delta = -event->angleDelta().y() * 0.5; // Adjust scroll speed
        
        QRectF rect = chart()->plotArea();
        qreal newLeft = rect.left() + delta;
        
        chart()->zoomIn(QRectF(newLeft, rect.top(), rect.width(), rect.height()));
        emit viewChanged();
        event->accept();
    }
}

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
    chartView_ = new ZoomableChartView();
    chartView_->setRenderHint(QPainter::Antialiasing);
    chartView_->setRubberBand(QChartView::HorizontalRubberBand); // Enable horizontal scrolling
    connect(chartView_, &ZoomableChartView::viewChanged, this, &DashboardPanel::SyncScrollBarToAxis);
    chartLayout->addWidget(chartView_);
    
    // Scroll bar for X-axis
    chartScrollBar_ = new QScrollBar(Qt::Horizontal);
    chartScrollBar_->setRange(0, 1000); // Will be updated dynamically
    chartScrollBar_->setValue(1000); // Start at the end
    connect(chartScrollBar_, &QScrollBar::valueChanged, this, &DashboardPanel::OnScrollBarChanged);
    chartScrollBar_->hide(); // Hidden by default since auto-scroll is enabled
    chartLayout->addWidget(chartScrollBar_);
    
    tabWidget_->addTab(chartTab_, "PID Regulator");
    
    // Protocol Test Tab
    protocolTab_ = new ProtocolTestPanel(connector_);
    tabWidget_->addTab(protocolTab_, "Protocol Tester");

    // IMU Tab
    imuTab_ = new IMUPanel(connector_);
    tabWidget_->addTab(imuTab_, "IMU");
    
    connect(tabWidget_, &QTabWidget::currentChanged, this, &DashboardPanel::OnTabChanged);
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
    } else {
        // In manual mode, don't auto-update the axis range
        // Just update the scroll bar to reflect new data availability
        UpdateScrollBar();
    }
}

void DashboardPanel::UpdateScrollBar() {
    // Calculate the total time range
    qreal maxTime = 0;
    for (int i = 0; i < 4; ++i) {
        if (!currentSeries_[i]->points().isEmpty()) {
            QPointF lastPoint = currentSeries_[i]->points().last();
            maxTime = qMax(maxTime, lastPoint.x());
        }
    }
    
    if (maxTime > 10000) { // Only show scroll bar if we have more than 10 seconds of data
        chartScrollBar_->setRange(0, 1000); // Fixed range for smooth scrolling
        chartScrollBar_->setSingleStep(10);
        chartScrollBar_->setPageStep(100);
        // Don't update position here - let user control it
    }
}

void DashboardPanel::SyncScrollBarToAxis() {
    if (autoScrollCheck_->isChecked()) return; // Don't sync in auto-scroll mode
    
    // Sync scroll bar position to match current axis range
    qreal minTime = std::numeric_limits<qreal>::max();
    qreal maxTime = 0;
    for (int i = 0; i < 4; ++i) {
        if (!currentSeries_[i]->points().isEmpty()) {
            const auto& points = currentSeries_[i]->points();
            for (const QPointF& point : points) {
                minTime = qMin(minTime, point.x());
                maxTime = qMax(maxTime, point.x());
            }
        }
    }
    
    if (maxTime > minTime) {
        qreal currentWindowSize = axisX_->max() - axisX_->min();
        qreal totalRange = maxTime - minTime;
        
        if (totalRange > currentWindowSize) {
            qreal scrollableRange = totalRange - currentWindowSize;
            qreal currentLeft = axisX_->min();
            qreal scrollPos = (currentLeft - minTime) * chartScrollBar_->maximum() / scrollableRange;
            scrollPos = qBound(0.0, scrollPos, (qreal)chartScrollBar_->maximum());
            
            chartScrollBar_->blockSignals(true);
            chartScrollBar_->setValue(scrollPos);
            chartScrollBar_->blockSignals(false);
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
        chartView_->setRubberBand(QChartView::NoRubberBand); // Disable manual scrolling when auto-scroll is on
        chartScrollBar_->hide(); // Hide scroll bar in auto-scroll mode
    } else {
        chart_->setAnimationOptions(QChart::SeriesAnimations); // Re-enable animations
        chartView_->setRubberBand(QChartView::HorizontalRubberBand); // Enable manual horizontal scrolling
        
        // When switching to manual mode, keep the current view
        // The axis range is already set, just update scroll bar
        UpdateScrollBar(); // Update scroll bar
        chartScrollBar_->show(); // Show scroll bar in manual mode
    }
}

void DashboardPanel::OnTicksChanged(int val) {
    // Just updates the value used in calculation
}

void DashboardPanel::OnScrollBarChanged(int value) {
    if (autoScrollCheck_->isChecked()) return; // Don't interfere with auto-scroll
    
    // Calculate the total time range
    qreal minTime = std::numeric_limits<qreal>::max();
    qreal maxTime = 0;
    for (int i = 0; i < 4; ++i) {
        if (!currentSeries_[i]->points().isEmpty()) {
            const auto& points = currentSeries_[i]->points();
            for (const QPointF& point : points) {
                minTime = qMin(minTime, point.x());
                maxTime = qMax(maxTime, point.x());
            }
        }
    }
    
    if (maxTime > minTime) {
        qreal currentWindowSize = axisX_->max() - axisX_->min(); // Use current zoom level
        qreal totalRange = maxTime - minTime;
        
        if (totalRange > currentWindowSize) {
            // Can scroll through history
            qreal scrollableRange = totalRange - currentWindowSize;
            qreal scrollPos = minTime + value * scrollableRange / chartScrollBar_->maximum();
            axisX_->setRange(scrollPos, scrollPos + currentWindowSize);
        } else {
            // Not enough data to scroll, show all data
            axisX_->setRange(minTime, maxTime);
        }
    }
}

void DashboardPanel::SetMaxRpm(int value) {
    if (axisY_) {
        axisY_->setRange(-value, value);
    }
}

void DashboardPanel::OnTabChanged(int index) {
    // Check if Protocol Tester tab is selected (index 1)
    bool isProtocolTester = (index == 1);
    protocolTab_->SetLoggingEnabled(isProtocolTester);
    emit ProtocolTesterTabActivated(isProtocolTester);
}
