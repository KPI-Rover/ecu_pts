#include "VirtualJoystick.h"

#include <QPainter>
#include <QMouseEvent>
#include <QResizeEvent>
#include <QtMath>

VirtualJoystick::VirtualJoystick(QWidget *parent)
    : QWidget(parent), position_(0, 0), pressed_(false), radius_(50) {
    setMinimumSize(100, 100);
    setMouseTracking(true);
}

void VirtualJoystick::paintEvent(QPaintEvent *event) {
    Q_UNUSED(event)

    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);

    int centerX = width() / 2;
    int centerY = height() / 2;
    radius_ = qMin(width(), height()) / 2 - 10;

    // Draw background circle
    painter.setPen(QPen(Qt::black, 2));
    painter.setBrush(QBrush(Qt::lightGray));
    painter.drawEllipse(centerX - radius_, centerY - radius_, radius_ * 2, radius_ * 2);

    // Draw center cross
    painter.setPen(QPen(Qt::gray, 1));
    painter.drawLine(centerX - radius_, centerY, centerX + radius_, centerY);
    painter.drawLine(centerX, centerY - radius_, centerX, centerY + radius_);

    // Draw position dot
    if (pressed_) {
        painter.setPen(QPen(Qt::blue, 2));
        painter.setBrush(QBrush(Qt::blue));
    } else {
        painter.setPen(QPen(Qt::red, 2));
        painter.setBrush(QBrush(Qt::red));
    }

    int dotX = centerX + position_.x() * radius_;
    int dotY = centerY + position_.y() * radius_;
    painter.drawEllipse(dotX - 10, dotY - 10, 20, 20);
}

void VirtualJoystick::mousePressEvent(QMouseEvent *event) {
    if (event->button() == Qt::LeftButton) {
        pressed_ = true;
        updatePosition(event->pos());
        update();
    }
}

void VirtualJoystick::mouseMoveEvent(QMouseEvent *event) {
    if (pressed_) {
        updatePosition(event->pos());
        update();
    }
}

void VirtualJoystick::mouseReleaseEvent(QMouseEvent *event) {
    if (event->button() == Qt::LeftButton) {
        pressed_ = false;
        position_ = QPointF(0, 0);
        emitPosition();
        update();
    }
}

void VirtualJoystick::resizeEvent(QResizeEvent *event) {
    Q_UNUSED(event)
    update();
}

void VirtualJoystick::updatePosition(const QPoint &pos) {
    int centerX = width() / 2;
    int centerY = height() / 2;

    double dx = pos.x() - centerX;
    double dy = pos.y() - centerY;
    double dist = qSqrt(dx * dx + dy * dy);

    if (dist > radius_) {
        dx = dx / dist * radius_;
        dy = dy / dist * radius_;
    }

    position_.setX(dx / radius_);
    position_.setY(dy / radius_);

    emitPosition();
}

void VirtualJoystick::emitPosition() {
    emit positionChanged(position_.x(), position_.y());
}