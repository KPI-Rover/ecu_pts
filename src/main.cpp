#include "MainWindow.h"
#include <QApplication>
#include <QIcon>
#include <QDebug>
#include <QFile>

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);
    
    // Set application properties for better window manager integration
    app.setOrganizationName("KPI-Rover");
    app.setApplicationName("ECU PTS");
    
    // Set application icon
    QIcon icon(":/kpi_rover_logo.png");
    if (icon.isNull()) {
        qCritical() << "Error: Failed to load icon from resource";
    } else {
        app.setWindowIcon(icon);
    }
    
    MainWindow window;
    window.show();
    
    return app.exec();
}
