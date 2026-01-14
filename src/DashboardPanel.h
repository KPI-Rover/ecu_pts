#pragma once

#include <QWidget>
#include <QtCharts/QChartView>
#include <QtCharts/QLineSeries>
#include <QtCharts/QValueAxis>
#include <QCheckBox>
#include <QSpinBox>
#include <QTabWidget>
#include <QScrollBar>
#include <vector>

class ECUConnector;
class ProtocolTestPanel;
class IMUPanel;

class ZoomableChartView : public QChartView {
    Q_OBJECT
public:
    explicit ZoomableChartView(QWidget *parent = nullptr);
    
signals:
    void viewChanged();

protected:
    void wheelEvent(QWheelEvent *event) override;
};

class DashboardPanel : public QWidget {
    Q_OBJECT

public:
    explicit DashboardPanel(ECUConnector* connector, QWidget *parent = nullptr);

public slots:
    void SetMaxRpm(int value);

signals:
    void ProtocolTesterTabActivated(bool activated);

private slots:
    void OnEncoderDataReceived(const std::vector<float>& encoders);
    void OnMotorSelectionChanged();
    void OnAutoScrollChanged(int state);
    void OnTicksChanged(int val);
    void OnScrollBarChanged(int value);
    void OnTabChanged(int index);

private:
    void SetupUi();
    void SetupChart();
    void UpdateScrollBar();
    void SyncScrollBarToAxis();

    ECUConnector* connector_;
    
    QTabWidget* tabWidget_;
    QWidget* chartTab_;
    ProtocolTestPanel* protocolTab_;
    IMUPanel* imuTab_;
    
    QCheckBox* motorChecks_[4];
    QCheckBox* autoScrollCheck_;
    QSpinBox* ticksSpin_;
    
    QChart* chart_;
    ZoomableChartView* chartView_;
    QScrollBar* chartScrollBar_;
    QValueAxis* axisX_;
    QValueAxis* axisY_;
    
    QLineSeries* setpointSeries_[4];
    QLineSeries* currentSeries_[4];
    
    std::vector<float> lastEncoders_;
    qint64 startTime_;
    
    // For RPM calculation
    struct MotorData {
        qint64 lastTime = 0;
        float lastEncoder = 0;
        float accumulatedTicks = 0;
    };
    MotorData motorData_[4];
    
    static constexpr int TICKS_PER_REV_DEFAULT = 1328;
};
