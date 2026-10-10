// The wallpaper's settings page (Desktop and Wallpaper, and Screen Locking > Appearance).
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.FormLayout {
    id: page

    property string cfg_Theme
    property string cfg_Channel
    property int cfg_Fps
    property string cfg_Logo
    property string cfg_Rainbow
    property real cfg_Glow
    property real cfg_Bloom
    property real cfg_BgGain
    property real cfg_Speed
    property real cfg_Density
    property real cfg_Hieroglyphs
    property bool cfg_Snow
    property string cfg_PauseUnder
    property real cfg_Scale
    property string cfg_ExtraArgs

    component Choice: QQC2.ComboBox {
        id: choice
        property var values: []
        property string value
        signal picked(string value)
        textRole: "text"
        model: values
        currentIndex: Math.max(0, values.findIndex(v => v.value === choice.value))
        onActivated: index => choice.picked(values[index].value)
    }

    component Amount: RowLayout {
        id: amount
        property real value
        property real from: 0
        property real to: 2
        signal moved(real value)
        QQC2.Slider {
            Layout.preferredWidth: Kirigami.Units.gridUnit * 12
            from: amount.from
            to: amount.to
            stepSize: 0.05
            value: amount.value
            onMoved: amount.moved(Math.round(value * 100) / 100)
        }
        QQC2.Label {
            text: amount.value.toFixed(2)
        }
    }

    Choice {
        Kirigami.FormData.label: "Theme:"
        values: [{ value: "nixos", text: "NixOS snow" }, { value: "matrix", text: "Matrix green" }]
        value: page.cfg_Theme
        onPicked: v => page.cfg_Theme = v
    }
    QQC2.TextField {
        Kirigami.FormData.label: "Channel:"
        text: page.cfg_Channel
        onTextEdited: page.cfg_Channel = text
    }
    QQC2.SpinBox {
        Kirigami.FormData.label: "Frames per second:"
        from: 1
        to: 240
        value: page.cfg_Fps
        onValueModified: page.cfg_Fps = value
    }
    Choice {
        Kirigami.FormData.label: "Logo:"
        values: [{ value: "", text: "As the theme has it" }, { value: "white", text: "White" },
                 { value: "colours", text: "Colours" }, { value: "none", text: "None" }]
        value: page.cfg_Logo
        onPicked: v => page.cfg_Logo = v
    }
    Choice {
        Kirigami.FormData.label: "Rainbow:"
        values: [{ value: "logo", text: "The logo" }, { value: "all", text: "Everything" },
                 { value: "off", text: "Off" }]
        value: page.cfg_Rainbow
        onPicked: v => page.cfg_Rainbow = v
    }
    Amount {
        Kirigami.FormData.label: "Background brightness:"
        value: page.cfg_BgGain
        onMoved: v => page.cfg_BgGain = v
    }
    Amount {
        Kirigami.FormData.label: "Glow in the centre:"
        value: page.cfg_Glow
        onMoved: v => page.cfg_Glow = v
    }
    Amount {
        Kirigami.FormData.label: "Glow around the symbols:"
        value: page.cfg_Bloom
        onMoved: v => page.cfg_Bloom = v
    }
    Amount {
        Kirigami.FormData.label: "Falling speed:"
        from: 0.25
        to: 4
        value: page.cfg_Speed
        onMoved: v => page.cfg_Speed = v
    }
    Amount {
        Kirigami.FormData.label: "Streams:"
        to: 2.3
        value: page.cfg_Density
        onMoved: v => page.cfg_Density = v
    }
    Amount {
        Kirigami.FormData.label: "Hieroglyphs:"
        to: 1
        value: page.cfg_Hieroglyphs
        onMoved: v => page.cfg_Hieroglyphs = v
    }
    QQC2.CheckBox {
        Kirigami.FormData.label: "Snow:"
        text: "Falling snowflakes"
        checked: page.cfg_Snow
        onToggled: page.cfg_Snow = checked
    }
    Choice {
        Kirigami.FormData.label: "Pause under:"
        values: [{ value: "maximized", text: "Maximized and full-screen windows" },
                 { value: "fullscreen", text: "Full-screen windows" }, { value: "never", text: "Never" }]
        value: page.cfg_PauseUnder
        onPicked: v => page.cfg_PauseUnder = v
    }
    Amount {
        Kirigami.FormData.label: "Resolution:"
        from: 0.25
        to: 1
        value: page.cfg_Scale
        onMoved: v => page.cfg_Scale = v
    }
    QQC2.TextField {
        Kirigami.FormData.label: "More options:"
        placeholderText: "--spin 240 --drift 0"
        text: page.cfg_ExtraArgs
        onTextEdited: page.cfg_ExtraArgs = text
    }
}
