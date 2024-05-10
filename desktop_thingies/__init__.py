import ctypes
import os

from pathlib import Path

binary_dir = str(Path(__file__).parent.parent / "bin")
os.environ["GI_TYPELIB_PATH"] = binary_dir
ctypes.CDLL(binary_dir + "/libgtk4-layer-shell.so")


from desktop_thingies.physics_object import Texture


import importlib

import sys
from desktop_thingies import constants
from desktop_thingies.client import Client
from desktop_thingies.physics_object import Texture


def main():
    if len(sys.argv) < 1:
        raise

    path = sys.argv[1].replace("/", ".")

    config = importlib.import_module(path)
    Client(config.objects).start()
