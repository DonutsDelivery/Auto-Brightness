import QtQuick 2.15
import QtQuick.Controls 2.15 as Controls
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.20 as Kirigami
import BrightnessControl 1.0

Kirigami.ApplicationWindow {
    id: root
    title: "Auto Brightness & Monitor Control"
    width: 900
    height: 650
    
    BrightnessController {
        id: controller
        
        onStatusChanged: function(message, type) {
            if (type === "success") {
                showPassiveNotification(message, "short")
            } else if (type === "error") {
                showPassiveNotification(message, "long")
            } else {
                showPassiveNotification(message, "short")
            }
        }
    }
    
    globalDrawer: Kirigami.GlobalDrawer {
        title: "Settings"
        titleIcon: "configure"
        isMenu: true
        
        actions: [
            Kirigami.Action {
                text: "Auto Brightness"
                icon.name: "brightness-high"
                onTriggered: pageStack.currentIndex = 0
            },
            Kirigami.Action {
                text: "Monitor Control"
                icon.name: "preferences-desktop-display"
                onTriggered: pageStack.currentIndex = 1
            },
            Kirigami.Action {
                separator: true
            },
            Kirigami.Action {
                text: "About"
                icon.name: "help-about"
                onTriggered: aboutDialog.open()
            }
        ]
    }
    
    pageStack.initialPage: [autoBrightnessPage, monitorControlPage]
    
    // Auto Brightness Page
    Component {
        id: autoBrightnessPage
        
        Kirigami.ScrollablePage {
            title: "Auto Brightness Settings"
            icon.name: "brightness-high"
            
            ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                
                // Main toggle
                Kirigami.FormLayout {
                    Layout.fillWidth: true
                    
                    Controls.Switch {
                        Kirigami.FormData.label: "Enable Auto Brightness:"
                        checked: controller.autoBrightnessEnabled
                        onCheckedChanged: controller.setAutoBrightnessEnabled(checked)
                    }
                }
                
                Kirigami.Separator {
                    Layout.fillWidth: true
                }
                
                // Location Settings
                Kirigami.Card {
                    Layout.fillWidth: true
                    
                    header: Kirigami.Heading {
                        text: "Location Settings"
                        level: 3
                        padding: Kirigami.Units.largeSpacing
                    }
                    
                    ColumnLayout {
                        spacing: Kirigami.Units.smallSpacing
                        
                        Controls.Switch {
                            id: locationSwitch
                            text: "Override location (use manual coordinates)"
                            checked: controller.locationOverride
                            onCheckedChanged: controller.setLocationOverride(checked)
                        }
                        
                        Kirigami.FormLayout {
                            enabled: locationSwitch.checked
                            
                            Controls.SpinBox {
                                id: latitudeSpinBox
                                Kirigami.FormData.label: "Latitude:"
                                from: -90000
                                to: 90000
                                stepSize: 1
                                value: controller.latitude * 1000
                                
                                validator: DoubleValidator {
                                    bottom: -90.0
                                    top: 90.0
                                    decimals: 6
                                }
                                
                                textFromValue: function(value, locale) {
                                    return (value / 1000).toFixed(6)
                                }
                                
                                valueFromText: function(text, locale) {
                                    return Math.round(parseFloat(text) * 1000)
                                }
                            }
                            
                            Controls.SpinBox {
                                id: longitudeSpinBox
                                Kirigami.FormData.label: "Longitude:"
                                from: -180000
                                to: 180000
                                stepSize: 1
                                value: controller.longitude * 1000
                                
                                validator: DoubleValidator {
                                    bottom: -180.0
                                    top: 180.0
                                    decimals: 6
                                }
                                
                                textFromValue: function(value, locale) {
                                    return (value / 1000).toFixed(6)
                                }
                                
                                valueFromText: function(text, locale) {
                                    return Math.round(parseFloat(text) * 1000)
                                }
                            }
                            
                            Controls.Button {
                                text: "Apply Location"
                                enabled: locationSwitch.checked
                                onClicked: {
                                    controller.setLocation(
                                        latitudeSpinBox.value / 1000,
                                        longitudeSpinBox.value / 1000
                                    )
                                }
                            }
                        }
                    }
                }
                
                // Brightness Range Settings
                Kirigami.Card {
                    Layout.fillWidth: true
                    
                    header: Kirigami.Heading {
                        text: "Brightness Range"
                        level: 3
                        padding: Kirigami.Units.largeSpacing
                    }
                    
                    Kirigami.FormLayout {
                        enabled: controller.autoBrightnessEnabled
                        
                        ColumnLayout {
                            Kirigami.FormData.label: "Night Brightness:"
                            
                            Controls.Slider {
                                id: minBrightnessSlider
                                Layout.fillWidth: true
                                from: 10
                                to: 80
                                value: controller.minBrightness
                                stepSize: 1
                                
                                Controls.Label {
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: Math.round(minBrightnessSlider.value) + "%"
                                }
                            }
                        }
                        
                        ColumnLayout {
                            Kirigami.FormData.label: "Day Brightness:"
                            
                            Controls.Slider {
                                id: maxBrightnessSlider
                                Layout.fillWidth: true
                                from: 50
                                to: 100
                                value: controller.maxBrightness
                                stepSize: 1
                                
                                Controls.Label {
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: Math.round(maxBrightnessSlider.value) + "%"
                                }
                            }
                        }
                    }
                }
                
                // Action Buttons
                RowLayout {
                    Layout.fillWidth: true
                    
                    Controls.Button {
                        text: "Apply Settings"
                        icon.name: "dialog-ok-apply"
                        Layout.fillWidth: true
                        onClicked: {
                            controller.setBrightnessRange(
                                minBrightnessSlider.value,
                                maxBrightnessSlider.value
                            )
                            controller.applySettings()
                        }
                    }
                    
                    Controls.Button {
                        text: "Refresh"
                        icon.name: "view-refresh"
                        onClicked: controller.refresh_monitors()
                    }
                }
            }
        }
    }
    
    // Monitor Control Page
    Component {
        id: monitorControlPage
        
        Kirigami.ScrollablePage {
            title: "Monitor Control"
            icon.name: "preferences-desktop-display"
            
            ColumnLayout {
                spacing: Kirigami.Units.largeSpacing
                
                // Monitor Selection
                Kirigami.Card {
                    Layout.fillWidth: true
                    
                    header: Kirigami.Heading {
                        text: "Monitor Selection"
                        level: 3
                        padding: Kirigami.Units.largeSpacing
                    }
                    
                    ColumnLayout {
                        Controls.ComboBox {
                            id: monitorCombo
                            Layout.fillWidth: true
                            model: controller.monitors
                            textRole: "name"
                            
                            onCurrentIndexChanged: {
                                if (currentIndex >= 0 && model[currentIndex]) {
                                    controller.selectMonitor(model[currentIndex].id)
                                }
                            }
                        }
                        
                        Controls.Button {
                            text: "Refresh Monitors"
                            icon.name: "view-refresh"
                            onClicked: controller.refresh_monitors()
                        }
                    }
                }
                
                // Basic Controls
                Kirigami.Card {
                    Layout.fillWidth: true
                    visible: monitorCombo.currentIndex >= 0
                    
                    header: Kirigami.Heading {
                        text: "Basic Controls"
                        level: 3
                        padding: Kirigami.Units.largeSpacing
                    }
                    
                    Kirigami.FormLayout {
                        ColumnLayout {
                            Kirigami.FormData.label: "Brightness:"
                            
                            Controls.Slider {
                                id: brightnessSlider
                                Layout.fillWidth: true
                                from: 0
                                to: 100
                                value: 50
                                stepSize: 1
                                
                                onPressedChanged: {
                                    if (!pressed && monitorCombo.currentIndex >= 0) {
                                        controller.setMonitorBrightness(
                                            controller.monitors[monitorCombo.currentIndex].id,
                                            Math.round(value)
                                        )
                                    }
                                }
                                
                                Controls.Label {
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: Math.round(brightnessSlider.value) + "%"
                                }
                            }
                        }
                        
                        ColumnLayout {
                            Kirigami.FormData.label: "Contrast:"
                            
                            Controls.Slider {
                                id: contrastSlider
                                Layout.fillWidth: true
                                from: 0
                                to: 100
                                value: 50
                                stepSize: 1
                                
                                onPressedChanged: {
                                    if (!pressed && monitorCombo.currentIndex >= 0) {
                                        controller.setMonitorContrast(
                                            controller.monitors[monitorCombo.currentIndex].id,
                                            Math.round(value)
                                        )
                                    }
                                }
                                
                                Controls.Label {
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: Math.round(contrastSlider.value) + "%"
                                }
                            }
                        }
                    }
                }
                
                // Input Sources
                Kirigami.Card {
                    Layout.fillWidth: true
                    visible: monitorCombo.currentIndex >= 0
                    
                    header: Kirigami.Heading {
                        text: "Input Sources"
                        level: 3
                        padding: Kirigami.Units.largeSpacing
                    }
                    
                    Flow {
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing
                        
                        Repeater {
                            model: {
                                if (monitorCombo.currentIndex >= 0 && controller.monitors[monitorCombo.currentIndex]) {
                                    var caps = controller.monitors[monitorCombo.currentIndex].capabilities
                                    var features = caps.features || {}
                                    var inputFeature = features["60"] || {}
                                    var values = inputFeature.values || {}
                                    
                                    var inputs = []
                                    for (var code in values) {
                                        inputs.push({code: code, name: values[code]})
                                    }
                                    return inputs
                                }
                                return []
                            }
                            
                            Controls.Button {
                                text: modelData.name
                                onClicked: {
                                    controller.setInputSource(
                                        controller.monitors[monitorCombo.currentIndex].id,
                                        modelData.code
                                    )
                                }
                            }
                        }
                    }
                }
                
                // Quick Presets
                Kirigami.Card {
                    Layout.fillWidth: true
                    
                    header: Kirigami.Heading {
                        text: "Quick Presets"
                        level: 3
                        padding: Kirigami.Units.largeSpacing
                    }
                    
                    RowLayout {
                        Controls.Button {
                            text: "Gaming Mode"
                            icon.name: "applications-games"
                            Layout.fillWidth: true
                            onClicked: {
                                if (monitorCombo.currentIndex >= 0) {
                                    brightnessSlider.value = 80
                                    contrastSlider.value = 75
                                }
                            }
                        }
                        
                        Controls.Button {
                            text: "Movie Mode"
                            icon.name: "applications-multimedia"
                            Layout.fillWidth: true
                            onClicked: {
                                if (monitorCombo.currentIndex >= 0) {
                                    brightnessSlider.value = 40
                                    contrastSlider.value = 60
                                }
                            }
                        }
                        
                        Controls.Button {
                            text: "Work Mode"
                            icon.name: "applications-office"
                            Layout.fillWidth: true
                            onClicked: {
                                if (monitorCombo.currentIndex >= 0) {
                                    brightnessSlider.value = 60
                                    contrastSlider.value = 70
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    // About Dialog
    Kirigami.AboutPage {
        id: aboutDialog
        aboutData: {
            "displayName": "Auto Brightness & Monitor Control",
            "productName": "brightness-control",
            "version": "2.0",
            "shortDescription": "Automatic brightness control and comprehensive monitor management",
            "homepage": "",
            "bugAddress": "",
            "authors": [
                {
                    "name": "Auto Brightness Team",
                    "emailAddress": "",
                }
            ],
            "licenses": [
                {
                    "name": "GPL v3",
                    "text": "This program is free software..."
                }
            ]
        }
    }
}