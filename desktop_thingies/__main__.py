from abc import abstractmethod

import pymunk

import ctypes

ctypes.CDLL("libgtk4-layer-shell.so")


from desktop_thingies.client import Client
from desktop_thingies.physics_object import Texture
import io

from PIL import Image


objects = [
    Texture(
        texture="reimu_fumo.png",
        scale=1 / 5,
        displays=["DP-3"],
    ),
]


Client(objects).start()
