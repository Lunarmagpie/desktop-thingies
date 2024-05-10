from abc import abstractmethod

import pymunk

import ctypes

ctypes.CDLL("libgtk4-layer-shell.so")


from desktop_thingies.client import Client
from desktop_thingies.physics_object import PhysicsObject, Circle
import io

from PIL import Image






objects = [
    PhysicsObject(
        color="#000000",
        shape=Circle(10, 5)
    )
]



Client(objects).start()
