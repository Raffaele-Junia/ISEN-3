import qrcode
url="https://pacman-raf.base44.app/"
qr = qrcode.make(url)
qr.save("test1.png")

