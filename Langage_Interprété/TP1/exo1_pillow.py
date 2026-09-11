from PIL import Image
im = Image.open("junia.png")

print(im.format, im.size, im.mode)
box = (900, 200, 1490, 494)
region = im.crop(box)

region.show()
region.save("junia-crop.png")