import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.19 as Kirigami
import BrightnessControl 1.0

Kirigami.ApplicationWindow {
    id: root
    title: "Auto Brightness & Monitor Control (Kirigami)"
    width: 900
    height: 650
    minimumWidth: 700
    minimumHeight: 500
    
    BrightnessController {
        id: controller
        
        onStatusChanged: {
            showPassiveNotification(message)
        }
    }
    
    pageStack.initialPage: Kirigami.ScrollablePage {
        title: "Auto Brightness & Monitor Control"
        
        ColumnLayout {
            width: parent.width
            spacing: Kirigami.Units.largeSpacing
            
            // Auto Brightness Section
            Kirigami.Card {
                Layout.fillWidth: true
                
                header: Kirigami.Heading {
                    text: "Auto Brightness Settings"
                    level: 2
                    padding: Kirigami.Units.largeSpacing
                }
                
                ColumnLayout {
                    spacing: Kirigami.Units.largeSpacing
                    
                    // Auto brightness toggle
                    CheckBox {
                        text: "Enable Auto Brightness"
                        checked: controller.autoBrightnessEnabled
                        onCheckedChanged: controller.autoBrightnessEnabled = checked
                    }
                    
                    // Brightness sliders
                    RowLayout {
                        Label {
                            text: "Night Brightness:"
                            Layout.preferredWidth: 150
                        }
                        Slider {
                            id: minSlider
                            Layout.fillWidth: true
                            from: 10
                            to: 80
                            value: controller.minBrightness
                            onValueChanged: controller.minBrightness = value
                        }
                        Label {
                            text: Math.round(minSlider.value) + "%"
                            Layout.preferredWidth: 50
                        }
                    }
                    
                    RowLayout {
                        Label {
                            text: "Day Brightness:"
                            Layout.preferredWidth: 150
                        }
                        Slider {
                            id: maxSlider
                            Layout.fillWidth: true
                            from: 50
                            to: 100
                            value: controller.maxBrightness
                            onValueChanged: controller.maxBrightness = value
                        }
                        Label {
                            text: Math.round(maxSlider.value) + "%"
                            Layout.preferredWidth: 50
                        }
                    }
                }
            }
            
            // Location Override Section
            Kirigami.Card {
                Layout.fillWidth: true
                
                header: Kirigami.Heading {
                    text: "Location Settings"
                    level: 2
                    padding: Kirigami.Units.largeSpacing
                }
                
                ColumnLayout {
                    spacing: Kirigami.Units.largeSpacing
                    
                    CheckBox {
                        text: "Override location (use manual coordinates)"
                        checked: controller.locationOverride
                    }
                    
                    RowLayout {
                        Label {
                            text: "Latitude:"
                            Layout.preferredWidth: 100
                        }
                        TextField {
                            Layout.preferredWidth: 150
                            text: controller.latitude
                            onTextChanged: controller.latitude = text
                            placeholderText: "e.g. 40.7128"
                        }
                    }
                    
                    RowLayout {
                        Label {
                            text: "Longitude:"
                            Layout.preferredWidth: 100
                        }
                        TextField {
                            Layout.preferredWidth: 150
                            text: controller.longitude
                            onTextChanged: controller.longitude = text
                            placeholderText: "e.g. -74.0060"
                        }
                    }
                }
            }
            
            // Monitor Control Section
            Kirigami.Card {
                Layout.fillWidth: true
                
                header: Kirigami.Heading {
                    text: "Monitor Control"
                    level: 2
                    padding: Kirigami.Units.largeSpacing
                }
                
                ColumnLayout {
                    spacing: Kirigami.Units.largeSpacing
                    
                    Label {
                        text: "Available Monitors: " + controller.monitors.length
                    }
                    
                    Button {
                        text: "Refresh Monitors"
                        onClicked: controller.refresh_monitors()
                    }
                    
                    Label {
                        text: "Advanced monitor controls available through DDC/CI"
                        color: Kirigami.Theme.disabledTextColor
                    }
                }
            }
            
            // Action Buttons
            RowLayout {
                Button {
                    text: "Restart Service"
                    icon.name: "view-refresh"
                    onClicked: controller.restartService()
                }
                
                Button {
                    text: "Close"
                    icon.name: "window-close"
                    onClicked: Qt.quit()
                }
            }
        }
    }
}