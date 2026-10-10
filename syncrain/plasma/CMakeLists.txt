# The QML module org.syncrain: one item, SyncRain, that draws the stream inside a Qt Quick window
# with the native wallpaper's own passes (syncrain/native/). The Plasma wallpaper package
# (package/) is QML around it. install.sh builds it; tests/plasma/ builds it with Nix's Qt.
cmake_minimum_required(VERSION 3.16)
project(syncrain_plasma LANGUAGES C CXX)

find_package(Qt6 6.5 REQUIRED COMPONENTS Core Gui Quick OpenGL)
find_package(PkgConfig REQUIRED)
pkg_check_modules(DBUS REQUIRED IMPORTED_TARGET dbus-1)
qt_standard_project_setup()

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(QT_QML_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/qml)
set(NATIVE ${CMAKE_CURRENT_SOURCE_DIR}/../native)

qt_add_qml_module(syncrainplugin
    URI org.syncrain
    VERSION 1.0
    PLUGIN_TARGET syncrainplugin
    SOURCES syncrainitem.cpp syncrainitem.h
            ${NATIVE}/passes.c ${NATIVE}/scene.c ${NATIVE}/timing.c ${NATIVE}/kwin.c ${NATIVE}/syncrain.h)

target_include_directories(syncrainplugin PRIVATE ${NATIVE})
# where `syncrain` is, when the package knows (Nix); else the PATH and ~/.local/bin
set(SYNCRAIN_COMMAND "" CACHE STRING "the syncrain command that makes scenes")
target_compile_definitions(syncrainplugin PRIVATE SYNCRAIN_COMMAND="${SYNCRAIN_COMMAND}")
target_link_libraries(syncrainplugin PRIVATE Qt6::Core Qt6::Gui Qt6::Quick Qt6::OpenGL PkgConfig::DBUS m)
