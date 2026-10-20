#include "rainitem.h"

#include <QCoreApplication>
#include <QFile>
#include <QOpenGLContext>
#include <QOpenGLFunctions>
#include <QOpenGLFramebufferObject>
#include <QPointer>
#include <QQuickOpenGLUtils>
#include <QQuickWindow>
#include <QScreen>
#include <QDir>

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fcntl.h>
#include <mutex>
#include <time.h>
#include <unistd.h>

#include "syncrain.h"

namespace {

void *glAddress(const char *name)
{
    return reinterpret_cast<void *>(QOpenGLContext::currentContext()->getProcAddress(name));
}

double nowSeconds()
{
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return (double)ts.tv_sec + ts.tv_nsec / 1e9;
}

// What scene_load allocates besides its map (scene_unmap frees the map and the uniforms).
void forget(struct scene *s)
{
    free(s->kwin_script);
    free(s->fallback);                        // one allocation, the strings inside it
    s->kwin_script = nullptr;
    s->fallback = nullptr;
}

// The drawing, on Qt Quick's render thread. One per item: each screen's view has its own context.
class SyncRainRenderer : public QQuickFramebufferObject::Renderer
{
public:
    ~SyncRainRenderer() override { release(); }

    void synchronize(QQuickFramebufferObject *item) override
    {
        auto *s = static_cast<SyncRain *>(item);
        m_item = s;
        m_armed = s->m_armed;
        m_wantPath = s->scene();
        m_wantGeneration = s->m_generation;
        m_fixedTime = s->fixedTime();
        m_lead = s->m_lead;
    }

    QOpenGLFramebufferObject *createFramebufferObject(const QSize &size) override
    {
        QOpenGLFramebufferObjectFormat format;
        format.setAttachment(QOpenGLFramebufferObject::NoAttachment);
        return new QOpenGLFramebufferObject(size, format);
    }

    void render() override
    {
        if (m_armed && m_generation != m_wantGeneration)
            load();
        QOpenGLFramebufferObject *fbo = framebufferObject();
        if (!fbo)
            return;
        if (!m_passes) {                      // nothing yet, or nothing to draw: see through to black
            QOpenGLFunctions *f = QOpenGLContext::currentContext()->functions();
            f->glClearColor(0.0f, 0.0f, 0.0f, 0.0f);
            f->glClear(GL_COLOR_BUFFER_BIT);
            return;
        }
        const double t = std::isnan(m_fixedTime) ? nowSeconds() + m_lead : m_fixedTime;
        passes_draw(m_passes, t, fbo->handle(), 0, 0, fbo->width(), fbo->height());
        QQuickOpenGLUtils::resetOpenGLState();
        tell([](SyncRain *item) { item->frameDrawn(); });
    }

private:
    // The item lives on the GUI thread, which may delete it while this thread draws: it is only
    // looked at there.
    template <typename F> void tell(F f)
    {
        QPointer<SyncRain> item = m_item;
        QMetaObject::invokeMethod(QCoreApplication::instance(), [item, f] { if (item) f(item.data()); },
                                  Qt::QueuedConnection);
    }

    void fail(const QString &why)
    {
        tell([why](SyncRain *item) { item->failed(why); });
    }

    void load()
    {
        m_generation = m_wantGeneration;
        release();
        if (m_wantPath.isEmpty()) {
            fail(QStringLiteral("no scene named"));
            return;
        }
        QOpenGLContext *ctx = QOpenGLContext::currentContext();
        if (!ctx) {
            fail(QStringLiteral("Qt Quick draws without OpenGL here (QSG_RHI_BACKEND?); syncrain needs OpenGL"));
            return;
        }
        static std::once_flag once;
        static bool loaded = false;
        static char loadWhy[256] = "";
        std::call_once(once, [] { loaded = passes_load_gl(glAddress, loadWhy, sizeof loadWhy); });
        if (!loaded) {
            fail(QString::fromUtf8(loadWhy));
            return;
        }
        const bool es = ctx->isOpenGLES();
        int major = 0, minor = 0;
        const char *renderer = nullptr;
        passes_gl_version(&major, &minor, &renderer);
        if (es ? major < 3 : (major < 3 || (major == 3 && minor < 3))) {
            fail(QStringLiteral("%1 %2.%3 is too old; syncrain needs %4")
                     .arg(es ? QStringLiteral("OpenGL ES") : QStringLiteral("OpenGL")).arg(major).arg(minor)
                     .arg(es ? QStringLiteral("OpenGL ES 3.0") : QStringLiteral("OpenGL 3.3")));
            return;
        }
        const int fd = open(QFile::encodeName(m_wantPath).constData(), O_RDONLY | O_CLOEXEC);
        if (fd < 0) {
            fail(QStringLiteral("the scene %1 cannot be read (install.sh --lock-screen makes it)").arg(m_wantPath));
            return;
        }
        char why[1024] = "";
        const bool ok = scene_load(&m_scene, fd, why, sizeof why);
        close(fd);
        if (!ok) {
            fail(QString::fromUtf8(why));
            return;
        }
        m_hasScene = true;
        const double rest = m_scene.lock_rest;
        tell([rest](SyncRain *item) { item->setRest(rest); });
        m_passes = passes_create(&m_scene, es, why, sizeof why);
        scene_unmap(&m_scene);                // the sources and pixels are on the card now
        QQuickOpenGLUtils::resetOpenGLState();
        if (!m_passes)
            fail(QString::fromUtf8(why));
    }

    void release()
    {
        if (m_passes) {
            passes_destroy(m_passes);
            QQuickOpenGLUtils::resetOpenGLState();
        }
        m_passes = nullptr;
        if (m_hasScene) {
            scene_unmap(&m_scene);
            forget(&m_scene);
        }
        m_hasScene = false;
    }

    QPointer<SyncRain> m_item;                // set in synchronize, while the GUI thread waits
    QString m_wantPath;
    int m_wantGeneration = 0, m_generation = 0;
    bool m_armed = false;
    double m_fixedTime = NAN, m_lead = 0.0;
    struct scene m_scene {};
    bool m_hasScene = false;
    struct passes *m_passes = nullptr;
};

} // namespace

QString SyncRain::defaultScene()
{
    const QString named = qEnvironmentVariable("SYNCRAIN_LOCK_SCENE");
    if (!named.isEmpty())
        return named;
    // syncrain/native.py, lock_scene_path: $XDG_STATE_HOME, else ~/.local/state
    QString base = qEnvironmentVariable("XDG_STATE_HOME");
    if (base.isEmpty())
        base = QDir::homePath() + QStringLiteral("/.local/state");
    return base + QStringLiteral("/syncrain/lock-screen.scene");
}

SyncRain::SyncRain(QQuickItem *parent)
    : QQuickFramebufferObject(parent), m_scene(defaultScene()), m_fixedTime(NAN)
{
    m_generation = 1;                         // the default scene, unless QML names another
    const QByteArray frozen = qgetenv("SYNCRAIN_TEST_TIME");    // tests/lockscreen: one known frame
    if (!frozen.isEmpty())
        m_fixedTime = frozen.toDouble();
    setMirrorVertically(true);                // the passes draw as to a window: row 0 at the bottom
    m_tick.setSingleShot(true);
    m_tick.setTimerType(Qt::PreciseTimer);
    connect(&m_tick, &QTimer::timeout, this, &SyncRain::tick);
    m_clock.start();
}

QQuickFramebufferObject::Renderer *SyncRain::createRenderer() const
{
    return new SyncRainRenderer;
}

void SyncRain::setScene(const QString &scene)
{
    if (scene == m_scene)
        return;
    m_scene = scene;
    m_generation++;
    Q_EMIT sceneChanged();
    setStatus(QStringLiteral("preparing"));
    update();
    m_next = 0.0;
    schedule();
}

void SyncRain::setFps(qreal fps)
{
    fps = std::clamp(fps, 1.0, 240.0);
    if (fps == m_fps)
        return;
    m_fps = fps;
    Q_EMIT fpsChanged();
    m_next = 0.0;
    schedule();
}

void SyncRain::setFixedTime(qreal time)
{
    if (time == m_fixedTime || (std::isnan(time) && std::isnan(m_fixedTime)))
        return;
    m_fixedTime = time;
    Q_EMIT fixedTimeChanged();
    update();
}

void SyncRain::setRest(double seconds)
{
    if (seconds == m_rest)
        return;
    m_rest = seconds;
    Q_EMIT restChanged();
}

void SyncRain::setStatus(const QString &status)
{
    if (status == m_status)
        return;
    m_status = status;
    Q_EMIT statusChanged();
}

void SyncRain::frameDrawn()
{
    m_frames++;
    Q_EMIT framesChanged();
    if (m_status == QStringLiteral("preparing")) {
        setStatus(QStringLiteral("drawing"));
        const QString screen = window() && window()->screen() ? window()->screen()->name() : QString();
        // one line in the journal (journalctl --user -b | grep syncrain) for each screen it starts on
        qInfo("syncrain: the lock screen draws the rain on %s", qPrintable(screen));
    }
}

void SyncRain::failed(const QString &why)
{
    qWarning("syncrain: the lock screen draws no rain: %s", qPrintable(why));
    setStatus(QStringLiteral("error: ") + why);
}

double SyncRain::refreshRate() const
{
    const double hz = window() && window()->screen() ? window()->screen()->refreshRate() : 60.0;
    return hz > 1.0 ? hz : 60.0;
}

// Frames land on whole refreshes, every nth so the rate stays at or under fps (pacing.py's step),
// timed from a fixed origin so the timer does not drift against the refresh.
void SyncRain::schedule()
{
    if (!m_armed || m_scene.isEmpty() || !std::isnan(m_fixedTime) || m_status.startsWith(QStringLiteral("error")))
        return;
    const double hz = refreshRate();
    const int step = std::max(1, (int)std::ceil(hz / m_fps - 1e-6));
    const double period = 1000.0 * step / hz;
    m_lead = 1.0 / hz;
    const double now = (double)m_clock.nsecsElapsed() / 1e6;
    if (m_next <= 0.0 || m_next < now - period)
        m_next = now;
    m_next += period;
    m_tick.start(std::max(0, (int)std::lround(m_next - now)));
}

void SyncRain::tick()
{
    if (isVisible() && window() && window()->isExposed()) {
        update();
        schedule();
    } else {                                  // not on screen (a screen off): look again soon, not at fps
        m_next = 0.0;
        m_tick.start(250);
    }
}

// The scene is loaded only once the window has shown a frame: compiling and uploading it takes a
// moment, and KWin gives the lock screen the keyboard only after its first frame, so the box comes
// first whatever the driver does with the rain.
void SyncRain::itemChange(ItemChange change, const ItemChangeData &value)
{
    QQuickFramebufferObject::itemChange(change, value);
    if (change != ItemSceneChange || !value.window)
        return;
    // QQuickWindow::graphicsApi() still says OpenGL when the software backend draws (kscreenlocker
    // retries a crashed greeter with QT_QUICK_BACKEND=software), so the backend is asked too
    if (QQuickWindow::graphicsApi() != QSGRendererInterface::OpenGL
        || QQuickWindow::sceneGraphBackend() == QStringLiteral("software")) {
        failed(QStringLiteral("Qt Quick draws without OpenGL here (software after a crash, or QSG_RHI_BACKEND); "
                              "syncrain's rain needs OpenGL"));
        return;
    }
    if (m_armed)
        return;
    QQuickWindow *w = value.window;
    QPointer<QQuickWindow> seen = w;              // queued: the window may be gone when this runs
    m_shown = connect(w, &QQuickWindow::frameSwapped, this, [this, seen] {
        disconnect(m_shown);
        if (!seen)
            return;
        QSGRendererInterface *ri = seen->rendererInterface();
        if (!ri || ri->graphicsApi() != QSGRendererInterface::OpenGL) {
            failed(QStringLiteral("Qt Quick draws this screen without OpenGL; syncrain's rain needs OpenGL"));
            return;
        }
        m_armed = true;
        update();
        m_next = 0.0;
        schedule();
    }, Qt::QueuedConnection);
}
