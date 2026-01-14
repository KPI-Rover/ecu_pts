#pragma once

#include <QMainWindow>
#include <QSplitter>
#include <QIcon>

class ECUConnector;
class ControlPanel;
class DashboardPanel;
class IMUPanel;

class MainWindow : public QMainWindow {
    Q_OBJECT

public:
    explicit MainWindow(QWidget *parent = nullptr);
    ~MainWindow();

private slots:
    void OnProtocolTesterTabActivated(bool activated);

private:
    void SetupUi();

    ECUConnector* connector_;
    ControlPanel* controlPanel_;
    DashboardPanel* dashboardPanel_;
    IMUPanel* imuPanel_;
    QSplitter* splitter_;
};
