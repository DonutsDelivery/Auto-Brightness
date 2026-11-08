import QtQuick 2.15
import QtQuick.Controls 2.15
import org.kde.kirigami 2.0 as Kirigami

Kirigami.ApplicationWindow {
    id: root
    title: "Kirigami Test"
    width: 400
    height: 300
    visible: true

    Kirigami.Page {
        title: "Test Page"
        
        Column {
            anchors.centerIn: parent
            spacing: 20
            
            Text {
                text: "Kirigami is working!"
                anchors.horizontalCenter: parent.horizontalCenter
            }
            
            Button {
                text: "Test Button"
                anchors.horizontalCenter: parent.horizontalCenter
            }
        }
    }
}