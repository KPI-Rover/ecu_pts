#pragma once

#include <QWidget>
#include <QPointF>

class VirtualJoystick : public QWidget {
    Q_OBJECT

public:
    explicit VirtualJoystick(QWidget *parent = nullptr);

signals:
    void positionChanged(double x, double y); // -1 to 1

protected:
    void paintEvent(QPaintEvent *event) override;
    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void mouseReleaseEvent(QMouseEvent *event) override;
    void resizeEvent(QResizeEvent *event) override;

private:
    void updatePosition(const QPoint &pos);
    void emitPosition();

    QPointF position_; // -1 to 1
    bool pressed_;
    int radius_;
};