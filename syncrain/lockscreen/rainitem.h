// SyncRain, the Qt Quick item the lock screen draws the stream with: the native wallpaper's passes
// (syncrain/native/passes.c) into the item's own framebuffer, on the OpenGL context Qt Quick gives
// kscreenlocker_greet. The scene (shaders, textures, uniforms) is the file `syncrain --write-scene`
// writes, the same Python code every other host uses, so the frame is the desktop's. The lock screen
// runs no Python: the scene is made beforehand (install.sh --lock-screen, and each wallpaper start).
// Revived from build 14's Plasma wallpaper item, without its KWin watch and its settings.
#pragma once

#include <QElapsedTimer>
#include <QQuickFramebufferObject>
#include <QTimer>
#include <QtQml/qqmlregistration.h>

class SyncRain : public QQuickFramebufferObject
{
    Q_OBJECT
    QML_ELEMENT
    // the scene file (default: $SYNCRAIN_LOCK_SCENE, else ~/.local/state/syncrain/lock-screen.scene);
    // unreadable: status says why and nothing is drawn
    Q_PROPERTY(QString scene READ scene WRITE setScene NOTIFY sceneChanged)
    Q_PROPERTY(qreal fps READ fps WRITE setFps NOTIFY fpsChanged)
    // a frozen clock (UNIX seconds) for tests; NaN: the real one
    Q_PROPERTY(qreal fixedTime READ fixedTime WRITE setFixedTime NOTIFY fixedTimeChanged)
    // "preparing", "drawing" or "error: <why>"
    Q_PROPERTY(QString status READ status NOTIFY statusChanged)
    Q_PROPERTY(int frames READ frames NOTIFY framesChanged)

public:
    explicit SyncRain(QQuickItem *parent = nullptr);
    Renderer *createRenderer() const override;
    static QString defaultScene();

    QString scene() const { return m_scene; }
    void setScene(const QString &scene);
    qreal fps() const { return m_fps; }
    void setFps(qreal fps);
    qreal fixedTime() const { return m_fixedTime; }
    void setFixedTime(qreal time);
    QString status() const { return m_status; }
    int frames() const { return m_frames; }

    // what the render thread copies in synchronize
    int m_generation = 0;
    double m_lead = 1.0 / 60.0;

    // from the render thread, queued
    Q_INVOKABLE void frameDrawn();
    Q_INVOKABLE void failed(const QString &why);

Q_SIGNALS:
    void sceneChanged();
    void fpsChanged();
    void fixedTimeChanged();
    void statusChanged();
    void framesChanged();

protected:
    void itemChange(ItemChange change, const ItemChangeData &value) override;

private:
    void setStatus(const QString &status);
    void schedule();
    void tick();
    double refreshRate() const;

    QString m_scene;
    qreal m_fps = 30.0;
    qreal m_fixedTime;
    QString m_status = QStringLiteral("preparing");
    int m_frames = 0;
    QTimer m_tick;
    QElapsedTimer m_clock;
    double m_next = 0.0;                  // when the next frame is due, in m_clock's milliseconds
};
