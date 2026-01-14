#include "MainWindow.h"
#include "ECUConnector.h"
#include "ControlPanel.h"
#include "DashboardPanel.h"

#include <QStatusBar>
#include <QMenuBar>

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent) {
    
    connector_ = new ECUConnector(this);
    
    SetupUi();
    
    setWindowTitle("ECU PTS - Performance Testing Software (C++)");
    setWindowIcon(QIcon(":/kpi_rover_logo.png"));
    resize(1200, 800);
    
    connect(connector_, &ECUConnector::ConnectionChanged, this, [this](bool connected){
        statusBar()->showMessage(connected ? "Connected to rover" : "Disconnected from rover");
    });
    
    connect(connector_, &ECUConnector::ErrorOccurred, this, [this](const QString& msg){
        statusBar()->showMessage("Error: " + msg, 5000);
    });
    
    statusBar()->showMessage("Not connected");
}

void MainWindow::OnProtocolTesterTabActivated(bool activated) {
    if (activated) {
        // Stop periodic updates
        controlPanel_->SetPeriodicUpdatesEnabled(false);
        
        // Send stop motors command
        if (connector_->IsConnected()) {
            std::vector<int> stopSpeeds(4, 0);
            connector_->SetAllMotorsSpeed(stopSpeeds);
        }
    } else {
        // Resume periodic updates
        controlPanel_->SetPeriodicUpdatesEnabled(true);
    }
}

MainWindow::~MainWindow() {
}

void MainWindow::SetupUi() {
    splitter_ = new QSplitter(Qt::Vertical, this);
    setCentralWidget(splitter_);
    
    dashboardPanel_ = new DashboardPanel(connector_, this);
    splitter_->addWidget(dashboardPanel_);
    
    controlPanel_ = new ControlPanel(connector_, this);
    splitter_->addWidget(controlPanel_);
    
    connect(controlPanel_, &ControlPanel::MaxRpmChanged, dashboardPanel_, &DashboardPanel::SetMaxRpm);
    dashboardPanel_->SetMaxRpm(controlPanel_->GetMaxRpm());
    
    connect(dashboardPanel_, &DashboardPanel::ProtocolTesterTabActivated, this, &MainWindow::OnProtocolTesterTabActivated);
    
    // 75% / 25% split
    splitter_->setStretchFactor(0, 3);
    splitter_->setStretchFactor(1, 1);
    
    // Initial sizes
    QList<int> sizes;
    sizes << 600 << 200;
    splitter_->setSizes(sizes);
}
