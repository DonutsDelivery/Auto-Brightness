# Maintainer: DonutsDelivery <megusta52@proton.me>
pkgname=auto-brightness
pkgver=1.0.0
pkgrel=1
pkgdesc="Automatic monitor brightness adjustment based on sunrise/sunset times"
arch=('any')
url="https://github.com/DonutsDelivery/auto-brightness"
license=('MIT')
depends=('python' 'python-requests' 'ddcutil')
makedepends=('git')
source=("auto_brightness.py"
        "brightness_control.py"
        "brightness_gui.py"
        "brightness_panel.py"
        "brightness_tray.py"
        "update_config.py"
        "plasmoid_helper.sh"
        "config.json"
        "auto-brightness.service")
sha256sums=('SKIP'
           'SKIP'
           'SKIP'
           'SKIP'
           'SKIP'
           'SKIP'
           'SKIP'
           'SKIP'
           'SKIP')

package() {
    cd "$srcdir"
    
    # Install Python scripts
    install -Dm755 auto_brightness.py "$pkgdir/usr/bin/auto-brightness"
    install -Dm755 brightness_control.py "$pkgdir/usr/share/auto-brightness/brightness_control.py"
    install -Dm755 brightness_gui.py "$pkgdir/usr/share/auto-brightness/brightness_gui.py"
    install -Dm755 brightness_panel.py "$pkgdir/usr/share/auto-brightness/brightness_panel.py"
    install -Dm755 brightness_tray.py "$pkgdir/usr/share/auto-brightness/brightness_tray.py"
    install -Dm755 update_config.py "$pkgdir/usr/share/auto-brightness/update_config.py"
    install -Dm755 plasmoid_helper.sh "$pkgdir/usr/share/auto-brightness/plasmoid_helper.sh"
    
    # Install config file
    install -Dm644 config.json "$pkgdir/etc/auto-brightness/config.json"
    
    # Install systemd service
    install -Dm644 auto-brightness.service "$pkgdir/usr/lib/systemd/user/auto-brightness.service"
}