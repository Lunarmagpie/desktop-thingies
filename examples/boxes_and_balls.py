import random
from desktop_thingies import Circle, Rectangle


def random_color():
    color = "#"
    for _ in range(6):
        color += random.choice("0123456789abcdef")
    return color


gravity = (0, 98)

objects = []

for _ in range(5):
    objects += [Circle(radius=150, friction=1, color=random_color())]
    objects += [Rectangle(width=500, height=200, friction=1, color=random_color())]
