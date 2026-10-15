# The QML module org.syncrain: one item, SyncRain, that draws the stream inside the lock screen with
# the native wallpaper's own passes (syncrain/native/). The shell package (package/) puts it behind
# syncrain's box. install.sh --lock-screen builds it; tests/lockscreen/ builds it with Nix's Qt.
cmake_minimum_required(VERSION 3.16)
project(syncrain_lockscreen LANGUAGES C CXX)

find_package(Qt6 6.5 REQUIRED COMPONENTS Core Gui Quick OpenGL)
qt_standard_project_setup()

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(QT_QML_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/qml)
set(NATIVE ${CMAKE_CURRENT_SOURCE_DIR}/../native)

qt_add_qml_module(syncrainplugin
    URI org.syncrain
    VERSION 1.0
    PLUGIN_TARGET syncrainplugin
    SOURCES rainitem.cpp rainitem.h
            ${NATIVE}/passes.c ${NATIVE}/scene.c ${NATIVE}/timing.c ${NATIVE}/syncrain.h)

target_include_directories(syncrainplugin PRIVATE ${NATIVE})
target_link_libraries(syncrainplugin PRIVATE Qt6::Core Qt6::Gui Qt6::Quick Qt6::OpenGL m)
