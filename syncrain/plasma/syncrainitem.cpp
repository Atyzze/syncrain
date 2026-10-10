#include "syncrainitem.h"

#include <QCryptographicHash>
#include <QDateTime>
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QOpenGLContext>
#include <QOpenGLFramebufferObject>
#include <QPointer>
#include <QProcess>
#include <QQuickOpenGLUtils>
#include <QQuickWindow>
#include <QScreen>
#include <QSocketNotifier>
#include <QStandardPaths>

#include <algorithm>
#include <cmath>
#include <fcntl.h>
#include <functional>
#include <malloc.h>
#include <mutex>
#include <sys/time.h>
#include <unistd.h>
#include <vector>

#include "syncrain.h"

namespace {

// ------------------------------------------------------------------ the scene

// The `syncrain` that makes scenes: $SYNCRAIN_COMMAND, else the one the package was built with
// (Nix), else the one on the PATH, else the one install.sh puts in ~/.local/bin (plasmashell's
// PATH may not have it).
QString syncrainCommand()
{
    const QString named = qEnvironmentVariable("SYNCRAIN_COMMAND");
    if (!named.isEmpty())
        return named;
    if (QFileInfo::exists(QStringLiteral(SYNCRAIN_COMMAND)))
        return QStringLiteral(SYNCRAIN_COMMAND);
    QString found = QStandardPaths::findExecutable(QStringLiteral("syncrain"));
    if (found.isEmpty())
        found = QStandardPaths::findExecutable(QStringLiteral("syncrain"),
                                               { QDir::homePath() + QStringLiteral("/.local/bin") });
    return found;
}

QString sceneDirectory()
{
    return QStandardPaths::writableLocation(QStandardPaths::GenericCacheLocation) + QStringLiteral("/syncrain");
}

// A scene is kept per command and options; a new syncrain (another path or mtime) makes new ones.
QString scenePathFor(const QString &command, const QStringList &arguments)
{
    QCryptographicHash hash(QCryptographicHash::Sha256);
    const QFileInfo info(command);
    hash.addData(info.canonicalFilePath().toUtf8());
    hash.addData(QByteArray::number(info.lastModified().toMSecsSinceEpoch()));
    for (const QString &a : arguments) {
        hash.addData(QByteArrayView("\0", 1));
        hash.addData(a.toUtf8());
    }
    return sceneDirectory() + QStringLiteral("/scene-") + QString::fromLatin1(hash.result().toHex().left(16))
           + QStringLiteral(".bin");
}

// A scene is about 19 MiB: the eight used last stay.
void pruneScenes()
{
    QDir dir(sceneDirectory());
    const QFileInfoList all = dir.entryInfoList({ QStringLiteral("scene-*.bin") }, QDir::Files, QDir::Time);
    for (int i = 8; i < all.size(); i++)
        QFile::remove(all[i].absoluteFilePath());
}

void touch(const QString &path)
{
    utimes(QFile::encodeName(path).constData(), nullptr);
}

QString kwinScriptOf(const QString &path)
{
    QString script;
    const int fd = open(QFile::encodeName(path).constData(), O_RDONLY | O_CLOEXEC);
    if (fd < 0)
        return script;
    struct scene s;
    char why[512];
    if (scene_load(&s, fd, why, sizeof why)) {
        script = QString::fromUtf8(s.kwin_script);
        scene_free(&s);
    }
    close(fd);
    return script;
}

// ------------------------------------------------------------------ KWin

// One watch for the process (plasmashell draws every screen's wallpaper): KWin says which screens
// a window covers, through the native wallpaper's own code (syncrain/native/kwin.c).
class Watch
{
public:
    static Watch *instance()
    {
        static Watch w;
        return &w;
    }

    void want(const QString &script)
    {
        if (script.isEmpty() || (script == m_script && (m_watch || m_failed)))
            return;
        stop();
        m_script = script;
        m_failed = false;
        m_watch = watch_new_named(&Watch::changed, "syncrain-plasma-watch");
        const QByteArray text = script.toUtf8();
        const char *why = m_watch ? watch_start(m_watch, text.constData(), true) : "out of memory";
        if (why) {
            qInfo("syncrain: %s; drawing goes on under covering windows", why);
            watch_free(m_watch);
            m_watch = nullptr;
            m_failed = true;
            return;
        }
        const int fd = watch_fd(m_watch);
        if (fd >= 0) {
            m_notifier = new QSocketNotifier(fd, QSocketNotifier::Read, &m_context);
            QObject::connect(m_notifier, &QSocketNotifier::activated, &m_context, [this] { watch_dispatch(m_watch); });
        }
        watch_dispatch(m_watch);
        QTimer::singleShot(1500, &m_context, [this] { check(false); });
    }

    bool hidden(const QString &screen) const
    {
        return m_watch && watch_hidden(m_watch, screen.toUtf8().constData());
    }

    void subscribe(QObject *who, std::function<void()> f) { m_subscribers.emplace_back(QPointer<QObject>(who), f); }

private:
    Watch() = default;

    static void changed()
    {
        auto &all = instance()->m_subscribers;
        for (size_t i = 0; i < all.size(); )
            if (all[i].first) {
                all[i].second();
                i++;
            } else {
                all.erase(all.begin() + (long)i);
            }
    }

    // the native wallpaper's watch_check: ask again once, then say so
    void check(bool retried)
    {
        if (!m_watch || watch_answered(m_watch))
            return;
        if (!retried) {
            watch_retry(m_watch);
            watch_dispatch(m_watch);
            QTimer::singleShot(1500, &m_context, [this] { check(true); });
            return;
        }
        qInfo("syncrain: KWin loaded the script but it reported nothing; drawing goes on under covering windows");
    }

    void stop()
    {
        delete m_notifier;
        m_notifier = nullptr;
        if (m_watch)
            watch_free(m_watch);
        m_watch = nullptr;
    }

    QObject m_context;
    struct watch *m_watch = nullptr;
    QSocketNotifier *m_notifier = nullptr;
    QString m_script;
    bool m_failed = false;
    std::vector<std::pair<QPointer<QObject>, std::function<void()>>> m_subscribers;
};

// ------------------------------------------------------------------ drawing, on the render thread

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

class SyncRainRenderer : public QQuickFramebufferObject::Renderer
{
public:
    ~SyncRainRenderer() override { release(); }

    void synchronize(QQuickFramebufferObject *item) override
    {
        auto *s = static_cast<SyncRain *>(item);
        m_item = s;
        m_wantPath = s->m_scenePath;
        m_wantGeneration = s->m_generation;
        m_fixedTime = s->fixedTime();
        m_lead = s->m_lead;
        if (s->renderScale() != m_scale) {
            m_scale = s->renderScale();
            invalidateFramebufferObject();
        }
    }

    QOpenGLFramebufferObject *createFramebufferObject(const QSize &size) override
    {
        QSize drawn = size;
        if (m_scale < 0.999)                  // app.py, RainArea._draw: smaller, then blown up
            drawn = QSize(std::max(64, (int)std::lround(size.width() * m_scale)),
                          std::max(36, (int)std::lround(size.height() * m_scale)));
        QOpenGLFramebufferObjectFormat format;
        format.setAttachment(QOpenGLFramebufferObject::NoAttachment);
        return new QOpenGLFramebufferObject(drawn, format);
    }

    void render() override
    {
        if (m_generation != m_wantGeneration)
            load();
        QOpenGLFramebufferObject *fbo = framebufferObject();
        if (!m_passes || !fbo)
            return;
        const double t = std::isnan(m_fixedTime) ? nowSeconds() + m_lead : m_fixedTime;
        passes_draw(m_passes, t, fbo->handle(), 0, 0, fbo->width(), fbo->height());
        QQuickOpenGLUtils::resetOpenGLState();
        if (m_item)
            QMetaObject::invokeMethod(m_item, "frameDrawn", Qt::QueuedConnection);
    }

private:
    void fail(const QString &why)
    {
        if (m_item)
            QMetaObject::invokeMethod(m_item, "failed", Qt::QueuedConnection, Q_ARG(QString, why));
    }

    void load()
    {
        m_generation = m_wantGeneration;
        release();
        if (m_wantPath.isEmpty())
            return;
        char why[1024] = "";
        static std::once_flag once;
        static bool loaded = false;
        static char loadWhy[256] = "";
        std::call_once(once, [] { loaded = passes_load_gl(glAddress, loadWhy, sizeof loadWhy); });
        if (!loaded) {
            fail(QString::fromUtf8(loadWhy));
            return;
        }
        QOpenGLContext *ctx = QOpenGLContext::currentContext();
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
            fail(QStringLiteral("the scene %1 cannot be read").arg(m_wantPath));
            return;
        }
        const bool ok = scene_load(&m_scene, fd, why, sizeof why);
        close(fd);
        if (!ok) {
            fail(QString::fromUtf8(why));
            return;
        }
        m_hasScene = true;
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
        if (m_hasScene)
            scene_free(&m_scene);
        m_hasScene = false;
    }

    QPointer<SyncRain> m_item;
    QString m_wantPath;
    int m_wantGeneration = 0, m_generation = 0;
    double m_fixedTime = NAN, m_lead = 0.0, m_scale = 1.0;
    struct scene m_scene {};
    bool m_hasScene = false;
    struct passes *m_passes = nullptr;
};

} // namespace

// ------------------------------------------------------------------ the item, on the GUI thread

SyncRain::SyncRain(QQuickItem *parent)
    : QQuickFramebufferObject(parent), m_fixedTime(NAN)
{
    const QByteArray frozen = qgetenv("SYNCRAIN_TEST_TIME");    // tests/plasma: the wallpaper package's frame
    if (!frozen.isEmpty())
        m_fixedTime = frozen.toDouble();
    setMirrorVertically(true);                // the passes draw as to a window: row 0 at the bottom
    m_prepare.setSingleShot(true);
    m_prepare.setInterval(400);               // a slider being dragged makes one scene, not twenty
    connect(&m_prepare, &QTimer::timeout, this, &SyncRain::prepareScene);
    m_tick.setSingleShot(true);
    m_tick.setTimerType(Qt::PreciseTimer);
    connect(&m_tick, &QTimer::timeout, this, &SyncRain::tick);
    m_clock.start();
    Watch::instance()->subscribe(this, [this] { updateCovered(); });
    // The shell's C heap keeps what the driver frees until asked: every five minutes it is handed
    // back, as the native wallpaper does (once for the process, whatever the number of screens).
    static QTimer *trim = nullptr;
    if (!trim && QCoreApplication::instance()) {
        trim = new QTimer(QCoreApplication::instance());
        trim->setInterval(300000);
        QObject::connect(trim, &QTimer::timeout, [] { malloc_trim(0); });
        trim->start();
    }
    m_prepare.start(0);
}

SyncRain::~SyncRain()
{
    if (m_process) {
        m_process->disconnect(this);
        m_process->kill();
        m_process->waitForFinished(1000);
    }
}

QQuickFramebufferObject::Renderer *SyncRain::createRenderer() const
{
    return new SyncRainRenderer;
}

void SyncRain::setArguments(const QStringList &arguments)
{
    if (arguments == m_arguments)
        return;
    m_arguments = arguments;
    Q_EMIT argumentsChanged();
    m_prepare.start();
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

void SyncRain::setRenderScale(qreal scale)
{
    scale = std::clamp(scale, 0.25, 1.0);
    if (scale == m_scale)
        return;
    m_scale = scale;
    Q_EMIT renderScaleChanged();
    update();
}

void SyncRain::setPauseUnder(const QString &pauseUnder)
{
    if (pauseUnder == m_pauseUnder)
        return;
    m_pauseUnder = pauseUnder;
    Q_EMIT pauseUnderChanged();
    m_prepare.start();                        // the KWin script is in the scene
}

void SyncRain::setWatchWindows(bool watch)
{
    if (watch == m_watchWindows)
        return;
    m_watchWindows = watch;
    Q_EMIT watchWindowsChanged();
    if (watching() && !m_scenePath.isEmpty())
        Watch::instance()->want(kwinScriptOf(m_scenePath));
    updateCovered();
}

void SyncRain::setFixedTime(qreal time)
{
    if (time == m_fixedTime || (std::isnan(time) && std::isnan(m_fixedTime)))
        return;
    m_fixedTime = time;
    Q_EMIT fixedTimeChanged();
    update();
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
        // one line in the journal (journalctl --user -b | grep syncrain) for each screen it starts on
        qInfo("syncrain: the Plasma wallpaper draws on %s in %s: %s", qPrintable(screenName()),
              qPrintable(QCoreApplication::applicationName()), qPrintable(m_arguments.join(QLatin1Char(' '))));
    }
}

void SyncRain::failed(const QString &why)
{
    qWarning("syncrain: %s", qPrintable(why));
    setStatus(QStringLiteral("error: ") + why);
}

// The scene for these options: from the cache, else made by `syncrain --write-scene`.
void SyncRain::prepareScene()
{
    const QStringList args = m_arguments + QStringList{ QStringLiteral("--pause-under"), m_pauseUnder };
    const QString command = syncrainCommand();
    if (command.isEmpty()) {
        failed(QStringLiteral("syncrain is not installed (install.sh puts it in ~/.local/bin)"));
        return;
    }
    const QString path = scenePathFor(command, args);
    if (QFileInfo::exists(path)) {
        touch(path);
        sceneReady(path);
        return;
    }
    if (m_process) {
        m_process->disconnect(this);
        m_process->kill();
        m_process->deleteLater();
    }
    QDir().mkpath(sceneDirectory());
    m_process = new QProcess(this);
    m_process->setProcessChannelMode(QProcess::MergedChannels);
    QProcess *p = m_process;
    connect(p, &QProcess::finished, this, [this, p, path](int code, QProcess::ExitStatus how) {
        const QString said = QString::fromUtf8(p->readAll()).trimmed();
        p->deleteLater();
        if (m_process == p)
            m_process = nullptr;
        if (how != QProcess::NormalExit || code != 0 || !QFileInfo::exists(path)) {
            failed(QStringLiteral("syncrain --write-scene failed: ") + said.right(300));
            return;
        }
        pruneScenes();
        sceneReady(path);
    });
    connect(p, &QProcess::errorOccurred, this, [this, p, command](QProcess::ProcessError error) {
        if (error == QProcess::FailedToStart && m_process == p)
            failed(QStringLiteral("%1 could not be started").arg(command));
    });
    setStatus(QStringLiteral("preparing"));
    p->start(command, QStringList{ QStringLiteral("--write-scene"), path } + args);
}

void SyncRain::sceneReady(const QString &path)
{
    m_scenePath = path;
    m_generation++;
    if (m_status.startsWith(QStringLiteral("error")))
        setStatus(QStringLiteral("preparing"));
    if (watching())
        Watch::instance()->want(kwinScriptOf(path));
    updateCovered();
    update();
    m_next = 0.0;
    schedule();
}

QString SyncRain::screenName() const
{
    return window() && window()->screen() ? window()->screen()->name() : QString();
}

double SyncRain::refreshRate() const
{
    const double hz = window() && window()->screen() ? window()->screen()->refreshRate() : 60.0;
    return hz > 1.0 ? hz : 60.0;
}

void SyncRain::updateCovered()
{
    const bool covered = watching() && Watch::instance()->hidden(screenName());
    if (covered == m_covered)
        return;
    m_covered = covered;
    Q_EMIT coveredChanged();
    if (!covered) {
        m_next = 0.0;
        schedule();
    }
}

// Frames land on whole refreshes, every nth so the rate stays at or under fps (pacing.py's step),
// timed from a fixed origin so the timer does not drift against the refresh.
void SyncRain::schedule()
{
    if (m_covered || m_scenePath.isEmpty() || !std::isnan(m_fixedTime))
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
    if (m_covered)
        return;
    if (isVisible() && window() && window()->isExposed())
        update();
    schedule();
}

void SyncRain::itemChange(ItemChange change, const ItemChangeData &value)
{
    QQuickFramebufferObject::itemChange(change, value);
    if (change == ItemSceneChange && value.window) {
        connect(value.window, &QQuickWindow::screenChanged, this, [this] { updateCovered(); });
        m_next = 0.0;
        schedule();
    }
}
