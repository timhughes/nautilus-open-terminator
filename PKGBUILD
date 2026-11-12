# Maintainer: Tim Hughes <thughes@thegoldfish.org>
pkgname=nautilus-open-terminator
pkgver=0.1.0
pkgrel=1
pkgdesc="Open Terminator from the Nautilus context menu"
arch=('any')
url="https://github.com/timhughes/nautilus-open-terminator"
license=('MPL-2.0')
depends=('nautilus-python' 'python' 'terminator')
makedepends=('gettext')
checkdepends=('python')
source=("$pkgname-$pkgver.tar.gz::https://github.com/timhughes/$pkgname/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

build() {
    cd "$srcdir/$pkgname-$pkgver"
    make
}

check() {
    cd "$srcdir/$pkgname-$pkgver"
    make check
}

package() {
    cd "$srcdir/$pkgname-$pkgver"
    make DESTDIR="$pkgdir" PREFIX=/usr install
    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
