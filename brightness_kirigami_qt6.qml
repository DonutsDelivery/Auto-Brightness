import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.19 as Kirigami
import BrightnessControl 1.0

Kirigami.ApplicationWindow {
    id: root
    title: "Monitor Remote Control"
    width: 900
    height: 700
    minimumWidth: 800
    minimumHeight: 600
    maximumWidth: 1200
    maximumHeight: 900
    color: "#2e3440"
    
    // Ensure window is visible and properly rendered
    visible: true
    opacity: 1.0
    
    // Force immediate render on startup with delay for proper initialization
    Timer {
        id: startupTimer
        interval: 100  // 100ms delay for proper initialization
        running: true
        repeat: false
        onTriggered: {
            // Ensure controller is initialized
            if (controller) {
                controller.refresh_monitors()
            }
            
            // Force window to front and ensure visibility
            requestActivate()
            if (typeof(show) === "function") {
                show()
            }
        }
    }
    
    Component.onCompleted: {
        // Immediate visibility setup
        visible = true
        opacity = 1.0
    }

    // Brightness preview throttle (500ms interval) - at root level for global access
    Timer {
        id: brightnessPreviewTimer
        interval: 500
        repeat: false
        onTriggered: {
            root.canPreview = true
        }
    }
    property int pendingBrightness: -1
    property bool canPreview: true

    function throttledPreview(brightness) {
        root.pendingBrightness = brightness
        if (root.canPreview) {
            controller.previewBrightness(brightness)
            root.canPreview = false
            brightnessPreviewTimer.start()
        }
    }

    BrightnessController {
        id: controller
        
        onStatusChanged: function(message, type) {
            // Only show important notifications to reduce visual noise
            if (type === "error" || message.includes("restarted")) {
                showPassiveNotification(message)
            }
        }
    }
    
    // Window focus handling to refresh content when window regains focus
    onActiveChanged: {
        if (active && controller) {
            // Window became active, refresh to prevent blank content
            Qt.callLater(function() {
                controller.refresh_monitors()
            })
        }
    }
    
    pageStack.initialPage: Kirigami.Page {
        title: "Monitor Remote Control"
        padding: 0
        
        Rectangle {
            anchors.fill: parent
            color: "#3b4252"
            
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Kirigami.Units.largeSpacing * 2
                spacing: Kirigami.Units.largeSpacing
            
                // Tab Bar
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 50
                    color: "#434c5e"
                    radius: 8
                    border.color: "#5e81ac"
                    border.width: 1
                    antialiasing: true
                    
                    TabBar {
                        id: tabBar
                        anchors.fill: parent
                        anchors.margins: 4
                        background: Rectangle { color: "transparent" }
                        
                        TabButton {
                            text: "Auto Brightness"
                            background: Rectangle {
                                color: parent.checked ? "#5e81ac" : "transparent"
                                radius: 6
                            }
                            contentItem: Text {
                                text: parent.text
                                color: "#eceff4"
                                font.bold: parent.checked
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                        TabButton {
                            text: "Monitor Control"
                            visible: controller.monitors.length > 0
                            background: Rectangle {
                                color: parent.checked ? "#5e81ac" : "transparent"
                                radius: 6
                            }
                            contentItem: Text {
                                text: parent.text
                                color: "#eceff4"
                                font.bold: parent.checked
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }
                
                // Tab Content Container
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "#434c5e"
                    radius: 12
                    border.color: "#5e81ac"
                    border.width: 1
                    antialiasing: true
                    
                    StackLayout {
                        anchors.fill: parent
                        anchors.margins: Kirigami.Units.largeSpacing
                        currentIndex: tabBar.currentIndex
                        
                        // Auto Brightness Tab
                        ScrollView {
                            clip: true
                            ScrollBar.vertical.policy: ScrollBar.AsNeeded
                            
                            ColumnLayout {
                                width: parent.parent.width - 40
                                spacing: Kirigami.Units.largeSpacing * 1.5
                                
                                // Main Control Card
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 120
                                    color: "#3b4252"
                                    radius: 12
                                    border.color: controller.autoBrightnessEnabled ? "#a3be8c" : "#bf616a"
                                    border.width: 2
                                    antialiasing: true
                                    
                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: Kirigami.Units.largeSpacing * 1.5
                                        spacing: Kirigami.Units.largeSpacing
                                        
                                        Switch {
                                            Layout.alignment: Qt.AlignHCenter
                                            text: "Auto Brightness"
                                            checked: controller.autoBrightnessEnabled
                                            onToggled: controller.autoBrightnessEnabled = checked
                                            font.pointSize: 14
                                            font.bold: true
                                        }
                                        
                                        Label {
                                            Layout.alignment: Qt.AlignHCenter
                                            text: controller.autoBrightnessEnabled ? 
                                                  "Automatically adjusting " + controller.monitors.length + " monitors" :
                                                  "Manual brightness control"
                                            color: "#d8dee9"
                                            font.italic: true
                                        }
                                    }
                                }
                                
                                // Solar Status & Brightness Visualization
                                Rectangle {
                                    id: solarStatusCard
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 150
                                    color: "#3b4252"
                                    radius: 12
                                    border.color: "#5e81ac"
                                    border.width: 1
                                    antialiasing: true
                                    clip: true

                                    // Auto-refresh solar data
                                    Timer {
                                        interval: 60000  // Update every minute
                                        running: true
                                        repeat: true
                                        onTriggered: solarStatusCard.refreshData()
                                    }

                                    function refreshData() {
                                        solarElevation = controller.getSolarElevation()
                                        brightnessPhase = controller.getBrightnessPhase()
                                        calculatedBrightness = controller.calculateCurrentBrightness(controller.maxBrightness)
                                    }

                                    property real solarElevation: controller.getSolarElevation()
                                    property string brightnessPhase: controller.getBrightnessPhase()
                                    property int calculatedBrightness: controller.calculateCurrentBrightness(controller.maxBrightness)

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 10

                                        // Top row: Sun icon, elevation, phase badge, and result
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 16

                                            // Sun/Moon icon with elevation
                                            RowLayout {
                                                spacing: 8

                                                Rectangle {
                                                    width: 36
                                                    height: 36
                                                    radius: 18
                                                    color: solarStatusCard.solarElevation > 0 ? "#ebcb8b" : "#81a1c1"
                                                    border.color: solarStatusCard.solarElevation > 0 ? "#d08770" : "#5e81ac"
                                                    border.width: 2

                                                    Label {
                                                        anchors.centerIn: parent
                                                        text: solarStatusCard.solarElevation > 0 ? "☀" : "☾"
                                                        font.pointSize: 16
                                                        color: "#2e3440"
                                                    }
                                                }

                                                ColumnLayout {
                                                    spacing: 0

                                                    Label {
                                                        text: "Sun Elevation"
                                                        font.pointSize: 9
                                                        color: "#d8dee9"
                                                    }

                                                    Label {
                                                        text: solarStatusCard.solarElevation.toFixed(1) + "°"
                                                        font.bold: true
                                                        font.pointSize: 14
                                                        color: "#eceff4"
                                                    }
                                                }
                                            }

                                            // Phase badge
                                            Rectangle {
                                                width: 75
                                                height: 28
                                                radius: 6
                                                color: {
                                                    var phase = solarStatusCard.brightnessPhase
                                                    if (phase === "Night") return "#4c566a"
                                                    if (phase === "Twilight") return "#b48ead"
                                                    if (phase === "Low Sun") return "#d08770"
                                                    if (phase === "Daylight") return "#ebcb8b"
                                                    return "#a3be8c"
                                                }

                                                Label {
                                                    anchors.centerIn: parent
                                                    text: solarStatusCard.brightnessPhase
                                                    font.bold: true
                                                    font.pointSize: 10
                                                    color: "#2e3440"
                                                }
                                            }

                                            Item { Layout.fillWidth: true }

                                            // Result
                                            ColumnLayout {
                                                spacing: 0
                                                Layout.alignment: Qt.AlignRight

                                                Label {
                                                    text: "Monitor Brightness"
                                                    font.pointSize: 9
                                                    color: "#d8dee9"
                                                    Layout.alignment: Qt.AlignRight
                                                }

                                                Label {
                                                    text: solarStatusCard.calculatedBrightness + "%"
                                                    font.bold: true
                                                    font.pointSize: 18
                                                    color: "#a3be8c"
                                                    Layout.alignment: Qt.AlignRight
                                                }
                                            }
                                        }

                                        // Progress bar
                                        Rectangle {
                                            Layout.fillWidth: true
                                            height: 10
                                            color: "#2e3440"
                                            radius: 5

                                            Rectangle {
                                                width: parent.width * (solarStatusCard.calculatedBrightness / 100)
                                                height: parent.height
                                                radius: 5
                                                gradient: Gradient {
                                                    orientation: Gradient.Horizontal
                                                    GradientStop { position: 0.0; color: "#5e81ac" }
                                                    GradientStop { position: 1.0; color: "#a3be8c" }
                                                }
                                                Behavior on width { NumberAnimation { duration: 300 } }
                                            }
                                        }

                                        // Elevation scaling toggle and brightness curve
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 8

                                            // Toggle for elevation scaling
                                            Rectangle {
                                                id: fullBrightToggle
                                                implicitWidth: fullBrightRow.implicitWidth + 16
                                                height: 38
                                                radius: 4
                                                color: "#2e3440"
                                                border.color: controller.useElevationScaling ? "#4c566a" : "#a3be8c"
                                                border.width: 1

                                                Row {
                                                    id: fullBrightRow
                                                    anchors.centerIn: parent
                                                    spacing: 4

                                                    CheckBox {
                                                        id: elevationScalingSwitch
                                                        checked: !controller.useElevationScaling
                                                        anchors.verticalCenter: parent.verticalCenter
                                                        onToggled: {
                                                            controller.useElevationScaling = !checked
                                                            solarStatusCard.refreshData()
                                                        }
                                                    }

                                                    Label {
                                                        text: "Full brightness"
                                                        font.pointSize: 8
                                                        color: elevationScalingSwitch.checked ? "#a3be8c" : "#d8dee9"
                                                        anchors.verticalCenter: parent.verticalCenter
                                                    }
                                                }
                                            }

                                            // Brightness curve as horizontal segments (elevation scaling mode)
                                            Repeater {
                                                model: [
                                                    { label: "Night", range: "< -6°", active: solarStatusCard.solarElevation <= -6, color: "#4c566a" },
                                                    { label: "Twilight", range: "-6° to 0°", active: solarStatusCard.solarElevation > -6 && solarStatusCard.solarElevation <= 0, color: "#b48ead" },
                                                    { label: "Low Sun", range: "0° to 15°", active: solarStatusCard.solarElevation > 0 && solarStatusCard.solarElevation <= 15, color: "#d08770" },
                                                    { label: "Daylight", range: "15° to 40°", active: solarStatusCard.solarElevation > 15 && solarStatusCard.solarElevation <= 40, color: "#ebcb8b" },
                                                    { label: "Bright", range: "> 40°", active: solarStatusCard.solarElevation > 40, color: "#a3be8c" }
                                                ]

                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    height: 38
                                                    radius: 4
                                                    color: modelData.active ? modelData.color : "#2e3440"
                                                    border.color: modelData.active ? modelData.color : "#4c566a"
                                                    border.width: 1
                                                    visible: controller.useElevationScaling

                                                    ColumnLayout {
                                                        anchors.centerIn: parent
                                                        spacing: 1

                                                        Label {
                                                            text: modelData.label
                                                            font.pointSize: 9
                                                            font.bold: modelData.active
                                                            color: modelData.active ? "#2e3440" : "#4c566a"
                                                            Layout.alignment: Qt.AlignHCenter
                                                        }

                                                        Label {
                                                            text: modelData.range
                                                            font.pointSize: 8
                                                            color: modelData.active ? "#2e3440" : "#4c566a"
                                                            Layout.alignment: Qt.AlignHCenter
                                                        }
                                                    }
                                                }
                                            }

                                            // Simple day/night cycle with twilight (full brightness mode)
                                            Repeater {
                                                model: [
                                                    { label: "Night", range: "< -6°", icon: "🌙", brightness: Math.round(controller.minBrightness) + "%", active: solarStatusCard.solarElevation <= -6, color: "#4c566a" },
                                                    { label: "Twilight", range: "-6° to 6°", icon: "🌅", brightness: "transition", active: solarStatusCard.solarElevation > -6 && solarStatusCard.solarElevation <= 6, color: "#b48ead" },
                                                    { label: "Day", range: "> 6°", icon: "☀️", brightness: Math.round(controller.maxBrightness) + "%", active: solarStatusCard.solarElevation > 6, color: "#ebcb8b" }
                                                ]

                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    height: 38
                                                    radius: 4
                                                    color: modelData.active ? modelData.color : "#2e3440"
                                                    border.color: modelData.active ? modelData.color : "#4c566a"
                                                    border.width: 1
                                                    visible: !controller.useElevationScaling

                                                    RowLayout {
                                                        anchors.centerIn: parent
                                                        spacing: 6

                                                        Label {
                                                            text: modelData.icon
                                                            font.pointSize: 12
                                                        }

                                                        ColumnLayout {
                                                            spacing: 0

                                                            Label {
                                                                text: modelData.label
                                                                font.pointSize: 9
                                                                font.bold: modelData.active
                                                                color: modelData.active ? "#2e3440" : "#4c566a"
                                                            }

                                                            Label {
                                                                text: modelData.range
                                                                font.pointSize: 8
                                                                color: modelData.active ? "#2e3440" : "#4c566a"
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                // Brightness Range Controls
                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: Kirigami.Units.largeSpacing

                                    // Night brightness
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 180
                                        color: "#3b4252"
                                        radius: 10
                                        border.color: minSlider.pressed ? "#ebcb8b" : "#81a1c1"
                                        border.width: minSlider.pressed ? 2 : 1
                                        antialiasing: true

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: Kirigami.Units.largeSpacing
                                            spacing: Kirigami.Units.largeSpacing

                                            RowLayout {
                                                Layout.fillWidth: true

                                                Rectangle {
                                                    width: minSlider.pressed ? 70 : 40
                                                    height: 20
                                                    color: minSlider.pressed ? "#ebcb8b" : "#81a1c1"
                                                    radius: 4

                                                    Behavior on width { NumberAnimation { duration: 150 } }
                                                    Behavior on color { ColorAnimation { duration: 150 } }

                                                    Label {
                                                        anchors.centerIn: parent
                                                        text: minSlider.pressed ? "PREVIEW" : "NIGHT"
                                                        color: "#2e3440"
                                                        font.bold: true
                                                        font.pointSize: 8
                                                    }
                                                }

                                                Label {
                                                    text: "Night Brightness"
                                                    font.bold: true
                                                    font.pointSize: 12
                                                    color: "#eceff4"
                                                }

                                                Item { Layout.fillWidth: true }

                                                Label {
                                                    text: Math.round(minSlider.value) + "%"
                                                    font.bold: true
                                                    font.pointSize: 16
                                                    color: minSlider.pressed ? "#ebcb8b" : "#81a1c1"

                                                    Behavior on color { ColorAnimation { duration: 150 } }
                                                }
                                            }

                                            Slider {
                                                id: minSlider
                                                Layout.fillWidth: true
                                                from: 5
                                                to: 80
                                                value: controller.minBrightness

                                                // Throttled preview while dragging (500ms interval)
                                                onMoved: {
                                                    root.throttledPreview(Math.round(value))
                                                }

                                                // Save and restore proper brightness when done
                                                onPressedChanged: {
                                                    if (!pressed) {
                                                        // Save the new value
                                                        controller.minBrightness = value
                                                        // Restore to current time-appropriate brightness
                                                        var currentBrightness = controller.calculateCurrentBrightness(controller.maxBrightness)
                                                        controller.previewBrightness(currentBrightness)
                                                        // Update the solar status card
                                                        solarStatusCard.refreshData()
                                                    }
                                                }
                                            }

                                            Label {
                                                Layout.alignment: Qt.AlignHCenter
                                                text: minSlider.pressed ? "Previewing night brightness..." : "When the sun is down"
                                                color: minSlider.pressed ? "#ebcb8b" : "#d8dee9"
                                                font.italic: true
                                                font.pointSize: 10

                                                Behavior on color { ColorAnimation { duration: 150 } }
                                            }
                                        }
                                    }
                                    
                                    // Day brightness
                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 180
                                        color: "#3b4252"
                                        radius: 10
                                        border.color: maxSlider.pressed ? "#ebcb8b" : "#d08770"
                                        border.width: maxSlider.pressed ? 2 : 1
                                        antialiasing: true

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: Kirigami.Units.largeSpacing
                                            spacing: Kirigami.Units.largeSpacing

                                            RowLayout {
                                                Layout.fillWidth: true

                                                Rectangle {
                                                    width: maxSlider.pressed ? 70 : 40
                                                    height: 20
                                                    color: maxSlider.pressed ? "#ebcb8b" : "#d08770"
                                                    radius: 4

                                                    Behavior on width { NumberAnimation { duration: 150 } }
                                                    Behavior on color { ColorAnimation { duration: 150 } }

                                                    Label {
                                                        anchors.centerIn: parent
                                                        text: maxSlider.pressed ? "PREVIEW" : "DAY"
                                                        color: "#2e3440"
                                                        font.bold: true
                                                        font.pointSize: 8
                                                    }
                                                }

                                                Label {
                                                    text: "Day Brightness"
                                                    font.bold: true
                                                    font.pointSize: 12
                                                    color: "#eceff4"
                                                }

                                                Item { Layout.fillWidth: true }

                                                Label {
                                                    text: Math.round(maxSlider.value) + "%"
                                                    font.bold: true
                                                    font.pointSize: 16
                                                    color: maxSlider.pressed ? "#ebcb8b" : "#d08770"

                                                    Behavior on color { ColorAnimation { duration: 150 } }
                                                }
                                            }

                                            Slider {
                                                id: maxSlider
                                                Layout.fillWidth: true
                                                from: 20
                                                to: 100
                                                value: controller.maxBrightness

                                                // Throttled preview while dragging (500ms interval)
                                                onMoved: {
                                                    // Preview the actual brightness that would apply at current solar position
                                                    var previewBrightness = controller.calculateCurrentBrightness(Math.round(value))
                                                    root.throttledPreview(previewBrightness)
                                                }

                                                // Save and restore proper brightness when done
                                                onPressedChanged: {
                                                    if (!pressed) {
                                                        // Save the new value
                                                        controller.maxBrightness = value
                                                        // Apply the new calculated brightness
                                                        var currentBrightness = controller.calculateCurrentBrightness(Math.round(value))
                                                        controller.previewBrightness(currentBrightness)
                                                        // Update the solar status card
                                                        solarStatusCard.refreshData()
                                                    }
                                                }
                                            }

                                            Label {
                                                Layout.alignment: Qt.AlignHCenter
                                                text: maxSlider.pressed ? "Previewing day brightness..." : "When the sun is up"
                                                color: maxSlider.pressed ? "#ebcb8b" : "#d8dee9"
                                                font.italic: true
                                                font.pointSize: 10

                                                Behavior on color { ColorAnimation { duration: 150 } }
                                            }
                                        }
                                    }
                                }

                                // Monitor Calibration Section
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: monitorCalibrationColumn.implicitHeight + 2 * Kirigami.Units.largeSpacing
                                    color: "#3b4252"
                                    radius: 10
                                    border.color: "#88c0d0"
                                    border.width: 1
                                    antialiasing: true

                                    ColumnLayout {
                                        id: monitorCalibrationColumn
                                        anchors.fill: parent
                                        anchors.margins: Kirigami.Units.largeSpacing
                                        spacing: Kirigami.Units.smallSpacing

                                        RowLayout {
                                            Layout.fillWidth: true

                                            Rectangle {
                                                width: 80
                                                height: 20
                                                color: "#88c0d0"
                                                radius: 4

                                                Label {
                                                    anchors.centerIn: parent
                                                    text: "CALIBRATE"
                                                    color: "#2e3440"
                                                    font.bold: true
                                                    font.pointSize: 8
                                                }
                                            }

                                            Label {
                                                text: "Monitor Brightness Offset"
                                                font.bold: true
                                                font.pointSize: 12
                                                color: "#eceff4"
                                            }

                                            Item { Layout.fillWidth: true }

                                            Button {
                                                text: "Refresh"
                                                icon.name: "view-refresh"
                                                onClicked: controller.refreshMonitorList()
                                            }
                                        }

                                        Label {
                                            Layout.fillWidth: true
                                            text: "Adjust individual monitor brightness to compensate for different panel characteristics"
                                            color: "#d8dee9"
                                            font.italic: true
                                            font.pointSize: 9
                                            wrapMode: Text.WordWrap
                                        }

                                        // Monitor list with offset sliders
                                        Repeater {
                                            model: controller.monitors

                                            Rectangle {
                                                Layout.fillWidth: true
                                                height: 60
                                                color: "#2e3440"
                                                radius: 6

                                                RowLayout {
                                                    anchors.fill: parent
                                                    anchors.margins: 10
                                                    spacing: 10

                                                    // Monitor icon and name
                                                    ColumnLayout {
                                                        Layout.preferredWidth: 180
                                                        spacing: 2

                                                        Label {
                                                            text: modelData.label || modelData.model || modelData.id
                                                            font.bold: true
                                                            font.pointSize: 10
                                                            color: "#eceff4"
                                                            elide: Text.ElideRight
                                                            Layout.fillWidth: true
                                                        }

                                                        Label {
                                                            text: modelData.id
                                                            font.pointSize: 8
                                                            color: "#4c566a"
                                                            elide: Text.ElideRight
                                                            Layout.fillWidth: true
                                                        }
                                                    }

                                                    // Offset slider
                                                    Slider {
                                                        id: offsetSlider
                                                        Layout.fillWidth: true
                                                        from: -50
                                                        to: 50
                                                        value: controller.getMonitorOffset(modelData.id)
                                                        stepSize: 1

                                                        onPressedChanged: {
                                                            if (!pressed) {
                                                                controller.setMonitorOffset(modelData.id, Math.round(value))
                                                            }
                                                        }
                                                    }

                                                    // Offset value display
                                                    Rectangle {
                                                        width: 50
                                                        height: 30
                                                        color: offsetSlider.value === 0 ? "#4c566a" : (offsetSlider.value > 0 ? "#a3be8c" : "#bf616a")
                                                        radius: 4

                                                        Label {
                                                            anchors.centerIn: parent
                                                            text: (offsetSlider.value > 0 ? "+" : "") + Math.round(offsetSlider.value) + "%"
                                                            font.bold: true
                                                            font.pointSize: 10
                                                            color: "#eceff4"
                                                        }
                                                    }
                                                }
                                            }
                                        }

                                        // No monitors message
                                        Label {
                                            Layout.fillWidth: true
                                            Layout.alignment: Qt.AlignHCenter
                                            visible: controller.monitors.length === 0
                                            text: "No monitors detected. Click Refresh to scan."
                                            color: "#4c566a"
                                            font.italic: true
                                            horizontalAlignment: Text.AlignHCenter
                                        }
                                    }
                                }

                                // Fullscreen Brightness Section
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: fullscreenColumn.implicitHeight + 2 * Kirigami.Units.largeSpacing
                                    color: "#3b4252"
                                    radius: 10
                                    border.color: controller.fullscreenBrightnessEnabled ? "#b48ead" : "#4c566a"
                                    border.width: 1
                                    antialiasing: true

                                    ColumnLayout {
                                        id: fullscreenColumn
                                        anchors.fill: parent
                                        anchors.margins: Kirigami.Units.largeSpacing
                                        spacing: Kirigami.Units.smallSpacing

                                        RowLayout {
                                            Layout.fillWidth: true

                                            Rectangle {
                                                width: 90
                                                height: 20
                                                color: controller.fullscreenBrightnessEnabled ? "#b48ead" : "#4c566a"
                                                radius: 4

                                                Label {
                                                    anchors.centerIn: parent
                                                    text: "FULLSCREEN"
                                                    color: "#2e3440"
                                                    font.bold: true
                                                    font.pointSize: 8
                                                }
                                            }

                                            Label {
                                                text: "Fullscreen Brightness"
                                                font.bold: true
                                                font.pointSize: 12
                                                color: "#eceff4"
                                            }

                                            Item { Layout.fillWidth: true }

                                            Switch {
                                                id: fullscreenSwitch
                                                checked: controller.fullscreenBrightnessEnabled
                                                onToggled: controller.fullscreenBrightnessEnabled = checked
                                            }
                                        }

                                        Label {
                                            Layout.fillWidth: true
                                            text: "Override brightness when an application goes fullscreen (e.g., games, videos)"
                                            color: "#d8dee9"
                                            font.italic: true
                                            font.pointSize: 9
                                            wrapMode: Text.WordWrap
                                        }

                                        // Fullscreen brightness slider
                                        Rectangle {
                                            Layout.fillWidth: true
                                            height: 70
                                            color: "#2e3440"
                                            radius: 6
                                            visible: controller.fullscreenBrightnessEnabled

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.margins: 10
                                                spacing: 15

                                                ColumnLayout {
                                                    Layout.preferredWidth: 100
                                                    spacing: 2

                                                    Label {
                                                        text: "Brightness"
                                                        font.bold: true
                                                        font.pointSize: 10
                                                        color: "#eceff4"
                                                    }

                                                    Label {
                                                        text: "When fullscreen"
                                                        font.pointSize: 8
                                                        color: "#4c566a"
                                                    }
                                                }

                                                Slider {
                                                    id: fullscreenSlider
                                                    Layout.fillWidth: true
                                                    from: 20
                                                    to: 100
                                                    value: controller.fullscreenBrightness
                                                    stepSize: 1

                                                    onPressedChanged: {
                                                        if (!pressed) {
                                                            controller.fullscreenBrightness = Math.round(value)
                                                        }
                                                    }
                                                }

                                                Rectangle {
                                                    width: 50
                                                    height: 30
                                                    color: "#b48ead"
                                                    radius: 4

                                                    Label {
                                                        anchors.centerIn: parent
                                                        text: Math.round(fullscreenSlider.value) + "%"
                                                        font.bold: true
                                                        font.pointSize: 10
                                                        color: "#2e3440"
                                                    }
                                                }
                                            }
                                        }

                                        Label {
                                            Layout.fillWidth: true
                                            visible: controller.fullscreenBrightnessEnabled
                                            text: "Polls every 5 seconds when enabled. Uses KWin to detect fullscreen windows."
                                            color: "#4c566a"
                                            font.pointSize: 8
                                            font.italic: true
                                        }
                                    }
                                }

                                // Service Control
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 80
                                    color: "#3b4252"
                                    radius: 10
                                    border.color: "#a3be8c"
                                    border.width: 1
                                    antialiasing: true

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: Kirigami.Units.largeSpacing
                                        spacing: Kirigami.Units.largeSpacing

                                        Rectangle {
                                            width: 60
                                            height: 30
                                            color: "#a3be8c"
                                            radius: 6

                                            Label {
                                                anchors.centerIn: parent
                                                text: "SERVICE"
                                                color: "#eceff4"
                                                font.bold: true
                                                font.pointSize: 9
                                            }
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 0

                                            Label {
                                                text: "Service Control"
                                                font.bold: true
                                                font.pointSize: 12
                                                color: "#eceff4"
                                            }

                                            Label {
                                                text: "Restart auto brightness service to apply changes"
                                                color: "#d8dee9"
                                                font.pointSize: 10
                                            }
                                        }
                                        
                                        Button {
                                            text: "Restart"
                                            onClicked: controller.restartService()
                                            highlighted: true
                                            Layout.preferredWidth: 100
                                            Layout.preferredHeight: 40
                                        }
                                    }
                                }
                                
                                // Location Settings
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 100
                                    color: "#3b4252"
                                    radius: 12
                                    border.color: controller.locationOverride ? "#ebcb8b" : "#a3be8c"
                                    border.width: 2
                                    antialiasing: true
                                    
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: Kirigami.Units.largeSpacing
                                        
                                        Label {
                                            text: "🌍"
                                            font.pointSize: 32
                                        }
                                        
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: Kirigami.Units.smallSpacing
                                            
                                            Label {
                                                text: controller.locationOverride ? "Manual Location" : "Auto Location"
                                                font.bold: true
                                                font.pointSize: 14
                                                color: "#eceff4"
                                            }
                                            
                                            Label {
                                                text: Number(controller.latitude).toFixed(2) + ", " + Number(controller.longitude).toFixed(2)
                                                color: "#d8dee9"
                                                font.family: "monospace"
                                                font.pointSize: 11
                                            }
                                        }
                                        
                                        Switch {
                                            text: "Manual"
                                            checked: controller.locationOverride
                                            Layout.alignment: Qt.AlignVCenter
                                        }
                                    }
                                }
                                
                                // City lookup
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 140
                                    color: "#3b4252"
                                    radius: 10
                                    border.color: "#88c0d0"
                                    border.width: 1
                                    antialiasing: true
                                    
                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: Kirigami.Units.largeSpacing
                                        spacing: Kirigami.Units.largeSpacing
                                        
                                        RowLayout {
                                            Layout.fillWidth: true
                                            
                                            Rectangle {
                                                width: 50
                                                height: 25
                                                color: "#88c0d0"
                                                radius: 4
                                                
                                                Label {
                                                    anchors.centerIn: parent
                                                    text: "SEARCH"
                                                    color: "#eceff4"
                                                    font.bold: true
                                                    font.pointSize: 8
                                                }
                                            }
                                            
                                            Label {
                                                text: "City Lookup"
                                                font.bold: true
                                                font.pointSize: 12
                                                color: "#eceff4"
                                            }
                                            
                                            Item { Layout.fillWidth: true }
                                        }
                                        
                                        Label {
                                            text: "Enter your city name to automatically get coordinates"
                                            color: "#d8dee9"
                                            font.italic: true
                                            font.pointSize: 10
                                        }
                                        
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: Kirigami.Units.largeSpacing
                                            
                                            TextField {
                                                id: cityField
                                                Layout.fillWidth: true
                                                placeholderText: "e.g. New York, London, Tokyo"
                                                selectByMouse: true
                                                
                                                Keys.onReturnPressed: {
                                                    controller.lookupCity(text)
                                                    text = ""
                                                }
                                            }
                                            
                                            Button {
                                                text: "Lookup"
                                                onClicked: {
                                                    controller.lookupCity(cityField.text)
                                                    cityField.text = ""
                                                }
                                                highlighted: true
                                                Layout.preferredWidth: 80
                                            }
                                        }
                                    }
                                }
                                
                                // Manual coordinate inputs
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 180
                                    color: "#3b4252"
                                    radius: 10
                                    border.color: "#b48ead"
                                    border.width: 1
                                    
                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: Kirigami.Units.largeSpacing
                                        spacing: Kirigami.Units.largeSpacing
                                        
                                        RowLayout {
                                            Layout.fillWidth: true
                                            
                                            Label {
                                                text: "▦"
                                                font.pointSize: 20
                                                color: "#b48ead"
                                                font.family: "monospace"
                                            }
                                            
                                            Label {
                                                text: "Manual Coordinates"
                                                font.bold: true
                                                font.pointSize: 12
                                                color: "#eceff4"
                                            }
                                            
                                            Item { Layout.fillWidth: true }
                                        }
                                        
                                        GridLayout {
                                            Layout.fillWidth: true
                                            columns: 3
                                            columnSpacing: Kirigami.Units.largeSpacing
                                            rowSpacing: Kirigami.Units.smallSpacing
                                            
                                            Label {
                                                text: "Latitude:"
                                                font.bold: true
                                                color: "#eceff4"
                                            }
                                            
                                            TextField {
                                                Layout.fillWidth: true
                                                text: Number(controller.latitude).toFixed(4)
                                                onEditingFinished: controller.latitude = parseFloat(text) || 0
                                                placeholderText: "40.7128"
                                                selectByMouse: true
                                            }
                                            
                                            Label {
                                                text: "(-90 to 90)"
                                                color: "#d8dee9"
                                                font.italic: true
                                                font.pointSize: 9
                                            }
                                            
                                            Label {
                                                text: "Longitude:"
                                                font.bold: true
                                                color: "#eceff4"
                                            }
                                            
                                            TextField {
                                                Layout.fillWidth: true
                                                text: Number(controller.longitude).toFixed(4)
                                                onEditingFinished: controller.longitude = parseFloat(text) || 0
                                                placeholderText: "-74.0060"
                                                selectByMouse: true
                                            }
                                            
                                            Label {
                                                text: "(-180 to 180)"
                                                color: "#d8dee9"
                                                font.italic: true
                                                font.pointSize: 9
                                            }
                                        }
                                    }
                                }
                                
                                Item { Layout.fillHeight: true }
                            }
                        }
                        
                        
                        // Monitor Control Tab  
                        ColumnLayout {
                            spacing: Kirigami.Units.largeSpacing
                            
                            // Monitor selection card
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 100
                                color: "#3b4252"
                                radius: 12
                                border.color: "#a3be8c"
                                border.width: 2
                                
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: Kirigami.Units.largeSpacing
                                    spacing: Kirigami.Units.largeSpacing
                                    
                                    Label {
                                        text: "🖥️"
                                        font.pointSize: 24
                                    }
                                    
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: Kirigami.Units.smallSpacing
                                        
                                        Label {
                                            text: "Monitor: " + (controller.monitors.length > 0 ? (controller.monitors[monitorCombo.currentIndex] ? controller.monitors[monitorCombo.currentIndex].name : "None") : "None")
                                            font.bold: true
                                            font.pointSize: 12
                                            color: "#eceff4"
                                        }
                                        
                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: Kirigami.Units.smallSpacing
                                            
                                            ComboBox {
                                                id: monitorCombo
                                                Layout.fillWidth: true
                                                model: controller.monitors
                                                textRole: "name"
                                                valueRole: "id"
                                                
                                                onCurrentValueChanged: {
                                                    if (currentValue) {
                                                        controller.currentMonitor = currentValue
                                                    }
                                                }
                                                
                                                Component.onCompleted: {
                                                    if (controller.monitors.length > 0) {
                                                        currentIndex = 0
                                                        controller.currentMonitor = controller.monitors[0].id
                                                    }
                                                }
                                            }
                                            
                                            Button {
                                                text: "Refresh"
                                                onClicked: controller.refresh_monitors()
                                                Layout.preferredWidth: 70
                                                Layout.preferredHeight: 30
                                            }
                                            
                                            Button {
                                                text: "Detect"
                                                onClicked: controller.detectMonitorCapabilities()
                                                highlighted: true
                                                Layout.preferredWidth: 70
                                                Layout.preferredHeight: 30
                                            }
                                        }
                                    }
                                }
                            }
                            
                            // Control categories sub-tabs
                            Rectangle {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                color: "#3b4252"
                                radius: 12
                                border.color: "#5e81ac"
                                border.width: 1
                                
                                ColumnLayout {
                                    anchors.fill: parent
                                    anchors.margins: Kirigami.Units.largeSpacing
                                    spacing: 0
                                    
                                    // Sub-tab bar
                                    TabBar {
                                        id: controlTabBar
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 40
                                        background: Rectangle { color: "transparent" }
                                        
                                        TabButton {
                                            text: "Display"
                                            background: Rectangle {
                                                color: parent.checked ? "#5e81ac" : "transparent"
                                                radius: 4
                                            }
                                            contentItem: Text {
                                                text: parent.text
                                                color: "#eceff4"
                                                font.bold: parent.checked
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                        }
                                        TabButton {
                                            text: "Color"
                                            background: Rectangle {
                                                color: parent.checked ? "#5e81ac" : "transparent"
                                                radius: 4
                                            }
                                            contentItem: Text {
                                                text: parent.text
                                                color: "#eceff4"
                                                font.bold: parent.checked
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                        }
                                        TabButton {
                                            text: "Input"
                                            background: Rectangle {
                                                color: parent.checked ? "#5e81ac" : "transparent"
                                                radius: 4
                                            }
                                            contentItem: Text {
                                                text: parent.text
                                                color: "#eceff4"
                                                font.bold: parent.checked
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                        }
                                        TabButton {
                                            text: "Advanced"
                                            background: Rectangle {
                                                color: parent.checked ? "#5e81ac" : "transparent"
                                                radius: 4
                                            }
                                            contentItem: Text {
                                                text: parent.text
                                                color: "#eceff4"
                                                font.bold: parent.checked
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                        }
                                    }
                                    
                                    // Sub-tab content
                                    StackLayout {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        currentIndex: controlTabBar.currentIndex
                                        
                                        // Display Controls Tab
                                        ScrollView {
                                            clip: true
                                            ScrollBar.vertical.policy: ScrollBar.AsNeeded
                                            
                                            ColumnLayout {
                                                width: parent.parent.width - 20
                                                spacing: Kirigami.Units.largeSpacing
                                                
                                                // Brightness Control
                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 120
                                                    color: "#434c5e"
                                                    radius: 8
                                                    border.color: "#d08770"
                                                    border.width: 1
                                                    visible: controller.currentMonitorCapabilities.includes("16") || controller.currentMonitorCapabilities.includes("10")
                                                    
                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: Kirigami.Units.largeSpacing
                                                        spacing: Kirigami.Units.smallSpacing
                                                        
                                                        RowLayout {
                                                            Layout.fillWidth: true
                                                            
                                                            Label {
                                                                text: "Brightness"
                                                                font.bold: true
                                                                color: "#eceff4"
                                                            }
                                                            
                                                            Item { Layout.fillWidth: true }
                                                            
                                                            Label {
                                                                text: Math.round(brightnessSlider.value) + "%"
                                                                font.bold: true
                                                                color: "#d08770"
                                                            }
                                                        }
                                                        
                                                        Slider {
                                                            id: brightnessSlider
                                                            Layout.fillWidth: true
                                                            from: 0
                                                            to: 100
                                                            value: 50
                                                            onPressedChanged: {
                                                                if (!pressed && controller.currentMonitor) {
                                                                    var vcpCode = controller.currentMonitorCapabilities.includes("10") ? 10 : 16
                                                                    controller.setMonitorValue(controller.currentMonitor, vcpCode, value)
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                                
                                                // Contrast Control
                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 120
                                                    color: "#434c5e"
                                                    radius: 8
                                                    border.color: "#81a1c1"
                                                    border.width: 1
                                                    visible: controller.currentMonitorCapabilities.includes("12")
                                                    
                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: Kirigami.Units.largeSpacing
                                                        spacing: Kirigami.Units.smallSpacing
                                                        
                                                        RowLayout {
                                                            Layout.fillWidth: true
                                                            
                                                            Label {
                                                                text: "Contrast"
                                                                font.bold: true
                                                                color: "#eceff4"
                                                            }
                                                            
                                                            Item { Layout.fillWidth: true }
                                                            
                                                            Label {
                                                                text: Math.round(contrastSlider.value) + "%"
                                                                font.bold: true
                                                                color: "#81a1c1"
                                                            }
                                                        }
                                                        
                                                        Slider {
                                                            id: contrastSlider
                                                            Layout.fillWidth: true
                                                            from: 0
                                                            to: 100
                                                            value: 75
                                                            onPressedChanged: {
                                                                if (!pressed && controller.currentMonitor) {
                                                                    controller.setMonitorValue(controller.currentMonitor, "12", value)
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                                
                                                Item { Layout.fillHeight: true }
                                            }
                                        }
                                        
                                        // Color Controls Tab
                                        ScrollView {
                                            clip: true
                                            ScrollBar.vertical.policy: ScrollBar.AsNeeded
                                            
                                            ColumnLayout {
                                                width: parent.parent.width - 20
                                                spacing: Kirigami.Units.largeSpacing
                                                
                                                // Color Presets
                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 160
                                                    color: "#434c5e"
                                                    radius: 8
                                                    border.color: "#b48ead"
                                                    border.width: 1
                                                    visible: controller.currentMonitorCapabilities.includes("14")
                                                    
                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: Kirigami.Units.largeSpacing
                                                        spacing: Kirigami.Units.smallSpacing
                                                        
                                                        Label {
                                                            text: "Color Presets"
                                                            font.bold: true
                                                            color: "#eceff4"
                                                        }
                                                        
                                                        GridLayout {
                                                            Layout.fillWidth: true
                                                            columns: 3
                                                            columnSpacing: Kirigami.Units.smallSpacing
                                                            rowSpacing: Kirigami.Units.smallSpacing
                                                            
                                                            Button {
                                                                text: "6500K"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "14", 5)
                                                                Layout.fillWidth: true
                                                            }
                                                            Button {
                                                                text: "9300K"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "14", 8)
                                                                Layout.fillWidth: true
                                                            }
                                                            Button {
                                                                text: "sRGB"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "14", 1)
                                                                Layout.fillWidth: true
                                                            }
                                                            Button {
                                                                text: "User 1"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "14", 11)
                                                                Layout.fillWidth: true
                                                            }
                                                            Button {
                                                                text: "User 2"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "14", 12)
                                                                Layout.fillWidth: true
                                                            }
                                                            Button {
                                                                text: "Native"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "14", 0)
                                                                Layout.fillWidth: true
                                                            }
                                                        }
                                                    }
                                                }
                                                
                                                // RGB Controls
                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 200
                                                    color: "#434c5e"
                                                    radius: 8
                                                    border.color: "#bf616a"
                                                    border.width: 1
                                                    antialiasing: true
                                                    visible: controller.currentMonitorCapabilities.includes("16") || controller.currentMonitorCapabilities.includes("18") || controller.currentMonitorCapabilities.includes("1A")
                                                    
                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: Kirigami.Units.largeSpacing
                                                        spacing: Kirigami.Units.smallSpacing
                                                        
                                                        Label {
                                                            text: "RGB Gain"
                                                            font.bold: true
                                                            color: "#eceff4"
                                                        }
                                                        
                                                        // Red
                                                        RowLayout {
                                                            Layout.fillWidth: true
                                                            visible: controller.currentMonitorCapabilities.includes("16")
                                                            
                                                            Label {
                                                                text: "Red:"
                                                                color: "#bf616a"
                                                                Layout.preferredWidth: 40
                                                            }
                                                            
                                                            Slider {
                                                                id: redSlider
                                                                Layout.fillWidth: true
                                                                from: 0
                                                                to: 100
                                                                value: 50
                                                                onPressedChanged: {
                                                                    if (!pressed && controller.currentMonitor) {
                                                                        controller.setMonitorValue(controller.currentMonitor, "16", value)
                                                                    }
                                                                }
                                                            }
                                                            
                                                            Label {
                                                                text: Math.round(redSlider.value) + "%"
                                                                color: "#bf616a"
                                                                Layout.preferredWidth: 40
                                                            }
                                                        }
                                                        
                                                        // Green
                                                        RowLayout {
                                                            Layout.fillWidth: true
                                                            visible: controller.currentMonitorCapabilities.includes("18")
                                                            
                                                            Label {
                                                                text: "Green:"
                                                                color: "#a3be8c"
                                                                Layout.preferredWidth: 40
                                                            }
                                                            
                                                            Slider {
                                                                id: greenSlider
                                                                Layout.fillWidth: true
                                                                from: 0
                                                                to: 100
                                                                value: 50
                                                                onPressedChanged: {
                                                                    if (!pressed && controller.currentMonitor) {
                                                                        controller.setMonitorValue(controller.currentMonitor, "18", value)
                                                                    }
                                                                }
                                                            }
                                                            
                                                            Label {
                                                                text: Math.round(greenSlider.value) + "%"
                                                                color: "#a3be8c"
                                                                Layout.preferredWidth: 40
                                                            }
                                                        }
                                                        
                                                        // Blue
                                                        RowLayout {
                                                            Layout.fillWidth: true
                                                            visible: controller.currentMonitorCapabilities.includes("1A")
                                                            
                                                            Label {
                                                                text: "Blue:"
                                                                color: "#81a1c1"
                                                                Layout.preferredWidth: 40
                                                            }
                                                            
                                                            Slider {
                                                                id: blueSlider
                                                                Layout.fillWidth: true
                                                                from: 0
                                                                to: 100
                                                                value: 50
                                                                onPressedChanged: {
                                                                    if (!pressed && controller.currentMonitor) {
                                                                        controller.setMonitorValue(controller.currentMonitor, "1A", value)
                                                                    }
                                                                }
                                                            }
                                                            
                                                            Label {
                                                                text: Math.round(blueSlider.value) + "%"
                                                                color: "#81a1c1"
                                                                Layout.preferredWidth: 40
                                                            }
                                                        }
                                                    }
                                                }
                                                
                                                // Color Temperature Control
                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 120
                                                    color: "#434c5e"
                                                    radius: 8
                                                    border.color: "#ebcb8b"
                                                    border.width: 1
                                                    antialiasing: true
                                                    visible: controller.currentMonitorCapabilities.includes("0B") || controller.currentMonitorCapabilities.includes("0C")
                                                    
                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: Kirigami.Units.largeSpacing
                                                        spacing: Kirigami.Units.smallSpacing
                                                        
                                                        Label {
                                                            text: "Color Temperature"
                                                            font.bold: true
                                                            color: "#eceff4"
                                                        }
                                                        
                                                        RowLayout {
                                                            Layout.fillWidth: true
                                                            spacing: Kirigami.Units.largeSpacing
                                                            
                                                            Button {
                                                                text: "Cooler"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "0B", 1)
                                                                Layout.fillWidth: true
                                                                visible: controller.currentMonitorCapabilities.includes("0B")
                                                            }
                                                            
                                                            Button {
                                                                text: "Warmer"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "0B", 2)
                                                                Layout.fillWidth: true
                                                                visible: controller.currentMonitorCapabilities.includes("0B")
                                                            }
                                                            
                                                            Button {
                                                                text: "Reset"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "0C", 0)
                                                                Layout.fillWidth: true
                                                                visible: controller.currentMonitorCapabilities.includes("0C")
                                                            }
                                                        }
                                                    }
                                                }
                                                
                                                Item { Layout.fillHeight: true }
                                            }
                                        }
                                        
                                        // Input Controls Tab
                                        ScrollView {
                                            clip: true
                                            ScrollBar.vertical.policy: ScrollBar.AsNeeded
                                            
                                            ColumnLayout {
                                                width: parent.parent.width - 20
                                                spacing: Kirigami.Units.largeSpacing
                                                
                                                // Input Source
                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 160
                                                    color: "#434c5e"
                                                    radius: 8
                                                    border.color: "#ebcb8b"
                                                    border.width: 1
                                                    antialiasing: true
                                                    visible: controller.currentMonitorCapabilities.includes("60")
                                                    
                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: Kirigami.Units.largeSpacing
                                                        spacing: Kirigami.Units.smallSpacing
                                                        
                                                        Label {
                                                            text: "Input Source"
                                                            font.bold: true
                                                            color: "#eceff4"
                                                        }
                                                        
                                                        GridLayout {
                                                            Layout.fillWidth: true
                                                            columns: 2
                                                            columnSpacing: Kirigami.Units.smallSpacing
                                                            rowSpacing: Kirigami.Units.smallSpacing
                                                            
                                                            Button {
                                                                text: "HDMI 1"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "60", 17)
                                                                Layout.fillWidth: true
                                                            }
                                                            Button {
                                                                text: "HDMI 2"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "60", 18)
                                                                Layout.fillWidth: true
                                                            }
                                                            Button {
                                                                text: "DisplayPort 1"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "60", 15)
                                                                Layout.fillWidth: true
                                                            }
                                                            Button {
                                                                text: "DisplayPort 2"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "60", 16)
                                                                Layout.fillWidth: true
                                                            }
                                                            Button {
                                                                text: "DVI"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "60", 3)
                                                                Layout.fillWidth: true
                                                            }
                                                            Button {
                                                                text: "VGA"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "60", 1)
                                                                Layout.fillWidth: true
                                                            }
                                                        }
                                                    }
                                                }
                                                
                                                // Power Control
                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 120
                                                    color: "#434c5e"
                                                    radius: 8
                                                    border.color: "#d08770"
                                                    border.width: 1
                                                    antialiasing: true
                                                    visible: controller.currentMonitorCapabilities.includes("214")
                                                    
                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: Kirigami.Units.largeSpacing
                                                        spacing: Kirigami.Units.smallSpacing
                                                        
                                                        Label {
                                                            text: "Power Control"
                                                            font.bold: true
                                                            color: "#eceff4"
                                                        }
                                                        
                                                        RowLayout {
                                                            Layout.fillWidth: true
                                                            spacing: Kirigami.Units.largeSpacing
                                                            
                                                            Button {
                                                                text: "On"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "214", 1)
                                                                highlighted: true
                                                                Layout.fillWidth: true
                                                            }
                                                            
                                                            Button {
                                                                text: "Standby"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "214", 4)
                                                                Layout.fillWidth: true
                                                            }
                                                            
                                                            Button {
                                                                text: "Off"
                                                                onClicked: controller.setMonitorValue(controller.currentMonitor, "214", 5)
                                                                Layout.fillWidth: true
                                                            }
                                                        }
                                                    }
                                                }
                                                
                                                Item { Layout.fillHeight: true }
                                            }
                                        }
                                        
                                        // Advanced Controls Tab
                                        ScrollView {
                                            clip: true
                                            ScrollBar.vertical.policy: ScrollBar.AsNeeded
                                            
                                            ColumnLayout {
                                                width: parent.parent.width - 40  // More space from edges
                                                height: parent.parent.height - 40  // Scale to container height
                                                anchors.margins: Kirigami.Units.largeSpacing  // Add margins around the content
                                                spacing: Kirigami.Units.largeSpacing * 1.5  // More spacing between sections
                                                
                                                // All Available VCP Codes
                                                Rectangle {
                                                    Layout.fillWidth: true
                                                    Layout.fillHeight: true  // Scale to fit available height
                                                    Layout.minimumHeight: 300  // Minimum height for usability
                                                    color: "#434c5e"
                                                    radius: 8
                                                    border.color: "#88c0d0"
                                                    border.width: 1
                                                    antialiasing: true
                                                    
                                                    ColumnLayout {
                                                        anchors.fill: parent
                                                        anchors.margins: Kirigami.Units.largeSpacing * 1.5  // More padding inside container
                                                        spacing: Kirigami.Units.largeSpacing
                                                        
                                                        Label {
                                                            text: "All Available VCP Codes"
                                                            font.bold: true
                                                            color: "#eceff4"
                                                            font.pointSize: 14  // Larger header
                                                        }
                                                        
                                                        Label {
                                                            text: "Direct access to all detected VCP features with contextual controls"
                                                            color: "#d8dee9"
                                                            font.italic: true
                                                            font.pointSize: 10
                                                            Layout.bottomMargin: Kirigami.Units.smallSpacing  // Space before list
                                                        }
                                                        
                                                        ListView {
                                                            Layout.fillWidth: true
                                                            Layout.fillHeight: true
                                                            clip: true
                                                            model: controller.currentMonitorCapabilities
                                                            spacing: Kirigami.Units.largeSpacing  // More space between items
                                                            topMargin: Kirigami.Units.smallSpacing  // Top padding in list
                                                            bottomMargin: Kirigami.Units.smallSpacing  // Bottom padding in list
                                                            leftMargin: Kirigami.Units.smallSpacing  // Left padding in list
                                                            rightMargin: Kirigami.Units.smallSpacing  // Right padding in list
                                                            
                                                            // Performance optimizations
                                                            cacheBuffer: 200  // Cache items for smooth scrolling
                                                            highlightRangeMode: ListView.ApplyRange  // Optimize highlight rendering
                                                            reuseItems: true  // Reuse delegate items for better performance
                                                            boundsBehavior: Flickable.StopAtBounds  // Optimize bounds behavior
                                                            
                                                            delegate: Rectangle {
                                                                property var featureInfo: controller.getFeatureInfo(modelData)
                                                                
                                                                width: ListView.view.width - (Kirigami.Units.smallSpacing * 2)  // Account for list margins
                                                                height: featureInfo.type === "readonly" ? 60 : 85  // Taller for better spacing
                                                                color: "#3b4252"
                                                                radius: 8  // Slightly more rounded
                                                                border.color: "#5e81ac"
                                                                border.width: 1
                                                                
                                                                // GPU acceleration optimizations
                                                                antialiasing: true  // Enable smooth edges with GPU
                                                                smooth: true  // Enable smooth scaling
                                                                layer.enabled: true  // Enable GPU layer acceleration
                                                                layer.effect: null  // No effect, just layer caching
                                                                
                                                                // Add subtle shadow effect (GPU optimized)
                                                                Rectangle {
                                                                    anchors.fill: parent
                                                                    anchors.topMargin: 2
                                                                    anchors.leftMargin: 2
                                                                    color: "#2e3440"
                                                                    radius: parent.radius
                                                                    z: parent.z - 1
                                                                    opacity: 0.3
                                                                    
                                                                    // GPU acceleration for shadow
                                                                    antialiasing: true
                                                                    layer.enabled: true
                                                                    layer.effect: null
                                                                }
                                                                
                                                                ColumnLayout {
                                                                    anchors.fill: parent
                                                                    anchors.margins: Kirigami.Units.largeSpacing * 1.2  // More padding
                                                                    spacing: Kirigami.Units.largeSpacing * 0.8  // Better internal spacing
                                                                    
                                                                    // Feature name and current value
                                                                    RowLayout {
                                                                        Layout.fillWidth: true
                                                                        spacing: Kirigami.Units.smallSpacing
                                                                        
                                                                        Rectangle {
                                                                            visible: featureInfo.type === "readonly"
                                                                            width: 8
                                                                            height: 8
                                                                            radius: 4
                                                                            color: "#ebcb8b"
                                                                            Layout.alignment: Qt.AlignVCenter
                                                                        }
                                                                        
                                                                        Label {
                                                                            text: featureInfo.name + (featureInfo.type === "readonly" ? " (Info)" : "")
                                                                            font.bold: true
                                                                            font.pointSize: 12
                                                                            color: featureInfo.type === "readonly" ? "#ebcb8b" : "#eceff4"
                                                                            Layout.fillWidth: true
                                                                        }
                                                                        
                                                                        Label {
                                                                            text: "VCP " + featureInfo.code
                                                                            font.pointSize: 9
                                                                            color: "#88c0d0"
                                                                            Layout.preferredWidth: 60
                                                                        }
                                                                        
                                                                        Label {
                                                                            property int currentValue: controller.getMonitorValue(controller.currentMonitor, modelData)
                                                                            text: featureInfo.type === "readonly" ? 
                                                                                  (currentValue > 0 ? currentValue + featureInfo.suffix : "N/A") :
                                                                                  currentValue + featureInfo.suffix
                                                                            font.pointSize: featureInfo.type === "readonly" ? 11 : 10
                                                                            font.bold: featureInfo.type === "readonly"
                                                                            color: featureInfo.type === "readonly" ? "#ebcb8b" : "#a3be8c"
                                                                            Layout.preferredWidth: featureInfo.type === "readonly" ? 90 : 70
                                                                        }
                                                                    }
                                                                    
                                                                    // Control based on feature type
                                                                    Item {
                                                                        Layout.fillWidth: true
                                                                        Layout.preferredHeight: featureInfo.type === "readonly" ? 0 : 40  // Slightly taller controls
                                                                        Layout.topMargin: featureInfo.type === "readonly" ? 0 : Kirigami.Units.smallSpacing  // Space above controls
                                                                        visible: featureInfo.type !== "readonly"
                                                                        
                                                                        // Slider for continuous values
                                                                        Slider {
                                                                            id: vcpSlider
                                                                            visible: featureInfo.type === "slider"
                                                                            anchors.fill: parent
                                                                            from: featureInfo.min
                                                                            to: featureInfo.max
                                                                            value: controller.getMonitorValue(controller.currentMonitor, modelData)
                                                                            stepSize: 1
                                                                            
                                                                            onMoved: {
                                                                                if (controller.currentMonitor) {
                                                                                    controller.setMonitorValue(controller.currentMonitor, modelData, Math.round(value))
                                                                                }
                                                                            }
                                                                        }
                                                                        
                                                                        // ComboBox for discrete values
                                                                        RowLayout {
                                                                            visible: featureInfo.type === "combo"
                                                                            anchors.fill: parent
                                                                            spacing: Kirigami.Units.largeSpacing  // Consistent spacing
                                                                            
                                                                            ComboBox {
                                                                                id: vcpCombo
                                                                                Layout.fillWidth: true
                                                                                Layout.preferredHeight: 38  // Consistent height
                                                                                
                                                                                property var valueMap: featureInfo.values
                                                                                model: {
                                                                                    var items = []
                                                                                    for (var key in valueMap) {
                                                                                        items.push(valueMap[key] + " (" + key + ")")
                                                                                    }
                                                                                    return items
                                                                                }
                                                                                
                                                                                onActivated: {
                                                                                    if (controller.currentMonitor && model[index]) {
                                                                                        var match = model[index].match(/\((\d+)\)$/)
                                                                                        if (match) {
                                                                                            controller.setMonitorValue(controller.currentMonitor, modelData, parseInt(match[1]))
                                                                                        }
                                                                                    }
                                                                                }
                                                                            }
                                                                        }
                                                                        
                                                                        // Stepper for incremental values
                                                                        RowLayout {
                                                                            visible: featureInfo.type === "stepper"
                                                                            anchors.fill: parent
                                                                            spacing: Kirigami.Units.largeSpacing  // More space between stepper elements
                                                                            
                                                                            Button {
                                                                                text: "−"
                                                                                Layout.preferredWidth: 40  // Slightly larger buttons
                                                                                Layout.preferredHeight: 38
                                                                                onClicked: {
                                                                                    if (controller.currentMonitor) {
                                                                                        var current = controller.getMonitorValue(controller.currentMonitor, modelData)
                                                                                        var newVal = Math.max(featureInfo.min, current - 1)
                                                                                        controller.setMonitorValue(controller.currentMonitor, modelData, newVal)
                                                                                    }
                                                                                }
                                                                            }
                                                                            
                                                                            TextField {
                                                                                id: vcpStepperInput
                                                                                Layout.fillWidth: true
                                                                                Layout.preferredHeight: 38  // Match button height
                                                                                text: controller.getMonitorValue(controller.currentMonitor, modelData)
                                                                                selectByMouse: true
                                                                                font.pointSize: 11
                                                                                horizontalAlignment: TextInput.AlignHCenter
                                                                                
                                                                                onEditingFinished: {
                                                                                    if (controller.currentMonitor) {
                                                                                        var val = Math.max(featureInfo.min, Math.min(featureInfo.max, parseInt(text) || 0))
                                                                                        controller.setMonitorValue(controller.currentMonitor, modelData, val)
                                                                                    }
                                                                                }
                                                                            }
                                                                            
                                                                            Button {
                                                                                text: "+"
                                                                                Layout.preferredWidth: 40  // Match other button
                                                                                Layout.preferredHeight: 38
                                                                                onClicked: {
                                                                                    if (controller.currentMonitor) {
                                                                                        var current = controller.getMonitorValue(controller.currentMonitor, modelData)
                                                                                        var newVal = Math.min(featureInfo.max, current + 1)
                                                                                        controller.setMonitorValue(controller.currentMonitor, modelData, newVal)
                                                                                    }
                                                                                }
                                                                            }
                                                                        }
                                                                        
                                                                        // Text field for unknown types
                                                                        RowLayout {
                                                                            visible: featureInfo.type === "textfield"
                                                                            anchors.fill: parent
                                                                            spacing: Kirigami.Units.largeSpacing  // Consistent spacing
                                                                            
                                                                            TextField {
                                                                                id: vcpInput
                                                                                Layout.fillWidth: true
                                                                                Layout.preferredHeight: 38  // Consistent height
                                                                                placeholderText: "Enter value (" + featureInfo.min + "-" + featureInfo.max + ")"
                                                                                selectByMouse: true
                                                                                font.pointSize: 11
                                                                            }
                                                                            
                                                                            Button {
                                                                                text: "Set"
                                                                                Layout.preferredWidth: 65  // Slightly wider
                                                                                Layout.preferredHeight: 38  // Consistent height
                                                                                highlighted: true
                                                                                onClicked: {
                                                                                    if (vcpInput.text && controller.currentMonitor) {
                                                                                        var val = Math.max(featureInfo.min, Math.min(featureInfo.max, parseInt(vcpInput.text) || 0))
                                                                                        controller.setMonitorValue(controller.currentMonitor, modelData, val)
                                                                                        vcpInput.clear()
                                                                                    }
                                                                                }
                                                                            }
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                
                // Bottom action bar
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 60
                    color: "#434c5e"
                    radius: 8
                    border.color: "#bf616a"
                    border.width: 1
                    
                    RowLayout {
                        anchors.centerIn: parent
                        spacing: Kirigami.Units.largeSpacing

                        Text {
                            text: "<a href='https://ko-fi.com/donutsdelivery' style='color: #88c0d0; text-decoration: none;'>Support on Ko-fi</a>"
                            color: "#d8dee9"
                            font.pixelSize: 12
                            onLinkActivated: Qt.openUrlExternally(link)
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: Qt.openUrlExternally("https://ko-fi.com/donutsdelivery")
                            }
                        }

                        Rectangle {
                            width: 1
                            height: 20
                            color: "#4c566a"
                        }

                        Button {
                            text: "Close Application"
                            onClicked: Qt.quit()
                            Layout.preferredWidth: 150
                            Layout.preferredHeight: 35
                        }
                    }
                }
            }
        }
    }
}