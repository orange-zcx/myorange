import os

print("==============================")
print("K210 SD CARD CHECK")
print("==============================")

paths = [
    "/",
    "/sd",
    "/sd/KPU",
    "/sd/KPU/mnist"
]

for path in paths:
    try:
        print("OK   ", path)
        print(os.listdir(path))
    except Exception as e:
        print("ERROR", path)
        print(e)

try:
    os.stat("/sd/KPU/mnist/uint8_mnist_cnn_model.kmodel")
    print("==============================")
    print("MODEL FOUND")
    print("==============================")
except Exception as e:
    print("==============================")
    print("MODEL NOT FOUND")
    print("/sd/KPU/mnist/uint8_mnist_cnn_model.kmodel")
    print("==============================")
