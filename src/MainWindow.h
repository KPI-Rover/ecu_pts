#pragma once

#include <QMainWindow>
#include <QSplitter>

class ECUConnector;
class ControlPanel;
class DashboardPanel;

class MainWindow : public QMainWindow {
    Q_OBJECT

public:
    explicit MainWindow(QWidget *parent = nullptr);
    ~MainWindow();

private:
    void SetupUi();

    ECUConnector* connector_;
    ControlPanel* controlPanel_;
    DashboardPanel* dashboardPanel_;
    QSplitter* splitter_;
};
