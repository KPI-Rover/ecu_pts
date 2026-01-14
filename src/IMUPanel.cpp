#include "IMUPanel.h"
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QPainter>
#include <QDateTime>
#include <cmath>
#include <QtCharts/QChart>
#include <QtCharts/QValueAxis>
#include <algorithm>
#include <QScrollArea>

IMUPanel::IMUPanel(ECUConnector* connector, QWidget *parent)
    : QWidget(parent), connector_(connector) {
    startTime_ = QDateTime::currentMSecsSinceEpoch();
    SetupUi();
    
    connect(connector_, &ECUConnector::ImuDataReceived, this, &IMUPanel::OnImuDataReceived);
}

void IMUPanel::SetupUi() {
    auto* outerLayout = new QVBoxLayout(this);
    auto* scrollArea = new QScrollArea(this);
    scrollArea->setWidgetResizable(true);
    scrollArea->setFrameShape(QFrame::NoFrame);
    
    auto* contentWidget = new QWidget();
    auto* mainLayout = new QVBoxLayout(contentWidget);
    
    auto* topLayout = new QHBoxLayout();
    compass_ = new CompassWidget(this);
    horizon_ = new HorizonWidget(this);
    topLayout->addWidget(compass_);
    topLayout->addWidget(horizon_);
    mainLayout->addLayout(topLayout);

    SetupCharts();
    mainLayout->addWidget(chartViewX_);
    mainLayout->addWidget(chartViewY_);
    mainLayout->addWidget(chartViewZ_);
    
    scrollArea->setWidget(contentWidget);
    outerLayout->addWidget(scrollArea);
}

void IMUPanel::SetupCharts() {
    seriesX_ = new QLineSeries();
    seriesY_ = new QLineSeries();
    seriesZ_ = new QLineSeries();

    chartViewX_ = CreateChart("Acceleration X", seriesX_, Qt::red);
    chartViewY_ = CreateChart("Acceleration Y", seriesY_, Qt::green);
    chartViewZ_ = CreateChart("Acceleration Z", seriesZ_, Qt::blue);
}

QChartView* IMUPanel::CreateChart(const QString& title, QLineSeries* series, QColor color) {
    auto* chart = new QChart();
    chart->addSeries(series);
    chart->setTitle(title);
    chart->legend()->hide();

    QPen pen(color);
    pen.setWidth(2);
    series->setPen(pen);

    auto* axisX = new QValueAxis();
    axisX->setTitleText("Time (s)");
    chart->addAxis(axisX, Qt::AlignBottom);
    series->attachAxis(axisX);

    auto* axisY = new QValueAxis();
    axisY->setTitleText("m/s²");
    chart->addAxis(axisY, Qt::AlignLeft);
    series->attachAxis(axisY);
    axisY->setRange(-15.0, 15.0); // Increased range to accommodate gravity (9.8 m/s²)

    auto* chartView = new QChartView(chart);
    chartView->setRenderHint(QPainter::Antialiasing);
    chartView->setMinimumHeight(120);
    return chartView;
}

void IMUPanel::OnImuDataReceived(const ImuData& data) {
    qreal currentTime = (QDateTime::currentMSecsSinceEpoch() - startTime_) / 1000.0;
    
    seriesX_->append(currentTime, data.accel_x);
    seriesY_->append(currentTime, data.accel_y);
    seriesZ_->append(currentTime, data.accel_z);

    // Keep only last 100 points
    if (seriesX_->count() > 100) {
        seriesX_->remove(0);
        seriesY_->remove(0);
        seriesZ_->remove(0);
    }

    // Update X axis range
    auto* axisX = static_cast<QValueAxis*>(chartViewX_->chart()->axes(Qt::Horizontal).first());
    if (seriesX_->count() > 0) {
        axisX->setRange(seriesX_->points().first().x(), seriesX_->points().last().x());
        static_cast<QValueAxis*>(chartViewY_->chart()->axes(Qt::Horizontal).first())->setRange(axisX->min(), axisX->max());
        static_cast<QValueAxis*>(chartViewZ_->chart()->axes(Qt::Horizontal).first())->setRange(axisX->min(), axisX->max());
    }

    // Quaternion to Euler
    float w = data.quat_w;
    float x = data.quat_x;
    float y = data.quat_y;
    float z = data.quat_z;

    float roll = std::atan2(2.0f * (w * x + y * z), 1.0f - 2.0f * (x * x + y * y));
    float pitch = std::asin(std::clamp(2.0f * (w * y - z * x), -1.0f, 1.0f));
    float yaw = std::atan2(2.0f * (w * z + x * y), 1.0f - 2.0f * (y * y + z * z));

    compass_->setYaw(yaw * 180.0f / M_PI);
    // Swapping roll and pitch as requested by user
    horizon_->setOrientation(pitch * 180.0f / M_PI, roll * 180.0f / M_PI);
}

// --- CompassWidget ---

void CompassWidget::paintEvent(QPaintEvent* event) {
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);
    
    int size = qMin(width(), height()) - 20;
    painter.translate(width()/2, height()/2);
    
    // Draw circle
    painter.setPen(QPen(Qt::black, 2));
    painter.drawEllipse(-size/2, -size/2, size, size);
    
    // Draw North marker
    painter.rotate(-yaw_);
    painter.setBrush(Qt::red);
    QPolygon northArrow;
    northArrow << QPoint(0, -size/2) << QPoint(-10, -size/2 + 20) << QPoint(10, -size/2 + 20);
    painter.drawPolygon(northArrow);
    
    painter.setBrush(Qt::blue);
    QPolygon southArrow;
    southArrow << QPoint(0, size/2) << QPoint(-10, size/2 - 20) << QPoint(10, size/2 - 20);
    painter.drawPolygon(southArrow);

    painter.setPen(Qt::black);
    painter.drawText(-10, -size/2 + 35, "N");
    painter.drawText(-10, size/2 - 25, "S");
}

// --- HorizonWidget ---

void HorizonWidget::paintEvent(QPaintEvent* event) {
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);
    
    int size = qMin(width(), height()) - 20;
    painter.translate(width()/2, height()/2);
    
    // Clip to circle
    QPainterPath path;
    path.addEllipse(-size/2, -size/2, size, size);
    painter.setClipPath(path);

    painter.rotate(-roll_);
    
    // Pitch offset (simple approximation)
    int pitchOffset = static_cast<int>(pitch_ * (size / 90.0f));
    
    // Draw Sky (Blue)
    painter.setBrush(QColor(135, 206, 235));
    painter.drawRect(-size, -size - pitchOffset, size*2, size + pitchOffset);
    
    // Draw Ground (Brown)
    painter.setBrush(QColor(139, 69, 19));
    painter.drawRect(-size, -pitchOffset, size*2, size + pitchOffset);
    
    // Draw Horizon line
    painter.setPen(QPen(Qt::white, 2));
    painter.drawLine(-size/2, -pitchOffset, size/2, -pitchOffset);
    
    // Aircraft symbol (static)
    painter.resetTransform();
    painter.translate(width()/2, height()/2);
    painter.setPen(QPen(Qt::yellow, 3));
    painter.drawLine(-20, 0, -5, 0);
    painter.drawLine(5, 0, 20, 0);
    painter.drawLine(0, 0, 0, 5);
}
