// SyncRain, a Qt Quick item that draws the stream: the native wallpaper's passes (passes.c) into
// the item's own framebuffer, on the OpenGL context Qt Quick renders the window with. The scene
// (shaders, textures, uniforms) comes from `syncrain --write-scene`, the same Python code every
// other host uses, so the frames are theirs.
#pragma once

#include <QElapsedTimer>
#include <QQuickFramebufferObject>
#include <QStringList>
#include <QTimer>
#include <QtQml/qqmlregistration.h>

class QProcess;

class SyncRain : public QQuickFramebufferObject
{
    Q_OBJECT
    QML_ELEMENT
    // syncrain's options for the picture (`--theme nixos --glow 0.5 ...`), as on its command line
    Q_PROPERTY(QStringList arguments READ arguments WRITE setArguments NOTIFY argumentsChanged)
    Q_PROPERTY(qreal fps READ fps WRITE setFps NOTIFY fpsChanged)
    Q_PROPERTY(qreal renderScale READ renderScale WRITE setRenderScale NOTIFY renderScaleChanged)
    // KWin: stop drawing under maximized or full-screen windows ("maximized"), full-screen ones
    // ("fullscreen") or never; and whether to ask KWin at all (the lock screen does not: nothing
    // covers it, and its scene is then the desktop's, already made)
    Q_PROPERTY(QString pauseUnder READ pauseUnder WRITE setPauseUnder NOTIFY pauseUnderChanged)
    Q_PROPERTY(bool watchWindows READ watchWindows WRITE setWatchWindows NOTIFY watchWindowsChanged)
    // a frozen clock (UNIX seconds) for tests; NaN: the real one
    Q_PROPERTY(qreal fixedTime READ fixedTime WRITE setFixedTime NOTIFY fixedTimeChanged)
    Q_PROPERTY(QString status READ status NOTIFY statusChanged)
    Q_PROPERTY(bool covered READ covered NOTIFY coveredChanged)
    Q_PROPERTY(int frames READ frames NOTIFY framesChanged)

public:
    explicit SyncRain(QQuickItem *parent = nullptr);
    ~SyncRain() override;
    Renderer *createRenderer() const override;

    QStringList arguments() const { return m_arguments; }
    void setArguments(const QStringList &arguments);
    qreal fps() const { return m_fps; }
    void setFps(qreal fps);
    qreal renderScale() const { return m_scale; }
    void setRenderScale(qreal scale);
    QString pauseUnder() const { return m_pauseUnder; }
    void setPauseUnder(const QString &pauseUnder);
    bool watchWindows() const { return m_watchWindows; }
    void setWatchWindows(bool watch);
    qreal fixedTime() const { return m_fixedTime; }
    void setFixedTime(qreal time);
    QString status() const { return m_status; }
    bool covered() const { return m_covered; }
    int frames() const { return m_frames; }

    // what the render thread copies in synchronize
    QString m_scenePath;
    int m_generation = 0;
    double m_lead = 1.0 / 60.0;

    // from the render thread, queued
    Q_INVOKABLE void frameDrawn();
    Q_INVOKABLE void failed(const QString &why);
    void sceneMissing(const QString &path);

Q_SIGNALS:
    void argumentsChanged();
    void fpsChanged();
    void renderScaleChanged();
    void pauseUnderChanged();
    void watchWindowsChanged();
    void fixedTimeChanged();
    void statusChanged();
    void coveredChanged();
    void framesChanged();

protected:
    void itemChange(ItemChange change, const ItemChangeData &value) override;

private:
    void prepareScene();
    void sceneReady(const QString &path);
    void setStatus(const QString &status);
    void schedule();
    void tick();
    void updateCovered();
    QString screenName() const;
    double refreshRate() const;

    QStringList m_arguments;
    qreal m_fps = 30.0;
    qreal m_scale = 1.0;
    QString m_pauseUnder = QStringLiteral("maximized");
    bool m_watchWindows = true;
    bool watching() const { return m_watchWindows && m_pauseUnder != QStringLiteral("never"); }
    qreal m_fixedTime;
    QString m_status = QStringLiteral("preparing");
    bool m_covered = false;
    int m_frames = 0;
    QProcess *m_process = nullptr;
    QString m_processPath;
    QTimer m_prepare;                     // arguments settle before a scene is made
    QTimer m_tick;
    QElapsedTimer m_clock;
    double m_next = 0.0;                  // when the next frame is due, in m_clock's milliseconds
};
