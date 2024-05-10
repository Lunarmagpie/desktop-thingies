import ctypes
import os
from pathlib import Path

import gi

# Setup GTK stuff. This is quite annoying but it needs to go here.
binary_dir = str(Path(__file__).parent / "bin")
os.environ["GI_TYPELIB_PATH"] = binary_dir
ctypes.CDLL(binary_dir + "/libgtk4-layer-shell.so")
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gtk4LayerShell", "1.0")

import importlib
import sys

from desktop_thingies import constants
from desktop_thingies.client import Client
from desktop_thingies.physics_object import Texture


def main():
    if len(sys.argv) < 1:
        raise

    path = Path(sys.argv[1])

    sys.path.append(str(path.parent))
    config = importlib.import_module(path.name.removesuffix(".py"))
    Client(config.objects).start()
