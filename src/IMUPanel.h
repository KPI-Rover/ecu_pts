#pragma once

#include <QWidget>
#include <QtCharts/QChartView>
#include <QtCharts/QLineSeries>
#include <QtCharts/QValueAxis>
#include "ECUConnector.h"

class CompassWidget;
class HorizonWidget;

class IMUPanel : public QWidget {
    Q_OBJECT
public:
    explicit IMUPanel(ECUConnector* connector, QWidget *parent = nullptr);

private slots:
    void OnImuDataReceived(const ImuData& data);

private:
    void SetupUi();
    void SetupCharts();
    QChartView* CreateChart(const QString& title, QLineSeries* series, QColor color);

    ECUConnector* connector_;
    
    CompassWidget* compass_;
    HorizonWidget* horizon_;

    QLineSeries* seriesX_;
    QLineSeries* seriesY_;
    QLineSeries* seriesZ_;
    QChartView* chartViewX_;
    QChartView* chartViewY_;
    QChartView* chartViewZ_;
    QValueAxis* axisX_;
    
    qint64 startTime_ = 0;
};

class CompassWidget : public QWidget {
    Q_OBJECT
public:
    explicit CompassWidget(QWidget* parent = nullptr) : QWidget(parent) {
        setMinimumSize(150, 150);
    }
    void setYaw(float yaw) { yaw_ = yaw; update(); }
protected:
    void paintEvent(QPaintEvent* event) override;
private:
    float yaw_ = 0;
};

class HorizonWidget : public QWidget {
    Q_OBJECT
public:
    explicit HorizonWidget(QWidget* parent = nullptr) : QWidget(parent) {
        setMinimumSize(150, 150);
    }
    void setOrientation(float roll, float pitch) { roll_ = roll; pitch_ = pitch; update(); }
protected:
    void paintEvent(QPaintEvent* event) override;
private:
    float roll_ = 0;
    float pitch_ = 0;
};
