import os
import image

TEMPLATE_PATH = "/flash/target_5.pgm"

print("==============================")
print("K210 FLASH TEMPLATE CHECK")
print("==============================")

try:
    print("ROOT:", os.listdir("/"))
except Exception as e:
    print("ROOT ERROR:", e)

try:
    print("FLASH:", os.listdir("/flash"))
except Exception as e:
    print("FLASH LIST ERROR:", e)

try:
    print("STAT:", os.stat(TEMPLATE_PATH))
except Exception as e:
    print("TEMPLATE STAT ERROR:", e)

try:
    file = open(TEMPLATE_PATH, "rb")
    header = file.read(16)
    file.close()
    print("HEADER READ OK:", header)
except Exception as e:
    print("TEMPLATE READ ERROR:", e)

try:
    template = image.Image(TEMPLATE_PATH)
    print("IMAGE LOAD OK:", template.width(), template.height())
    del template
except Exception as e:
    print("IMAGE LOAD ERROR:", e)

print("==============================")
print("CHECK FINISHED")
print("==============================")
