import argparse
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
from desktop_thingies.physics_object import Texture, Rectangle, Circle

__all__ = (
    "Texture",
    "Rectangle",
    "Circle",
)


def main():
    parser = argparse.ArgumentParser(
        prog="desktop-thingies", description="Add objects to your desktop."
    )

    parser.add_argument(
        "-c", "--config", help="The python file to use as the config file."
    )

    args = parser.parse_args()

    config = args.config
    if not config:
        if config_path := os.environ.get("XDG_CONFIG_HOME"):
            config = Path(config) / "desktop-thingies" / "config.py"
        else:
            config = (
                Path(os.environ["HOME"]) / ".config" / "desktop-thingies" / "config.py"
            )
    else:
        config = Path(args.config)

    sys.path.append(str(config.parent))
    try:
        config = importlib.import_module(config.name.removesuffix(".py"))
    except ImportError:
        print(f"Config file '{str(config)}' not found.")
        exit(1)

    Client(
        objects=config.objects,
        monitor=getattr(config, "monitor", None),
        target_framerate=getattr(config, "framerate", None),
        gravity=getattr(config, "gravity", (0,0)),
        wall_elasticity=getattr(config, "wall_elasticity", 0.5),
        wall_friction=getattr(config, "wall_friction", 0.5),
        top_offset=getattr(config, "top_offset", 0),
        bottom_offset=getattr(config, "bottom_offset", 0),
        left_offset=getattr(config, "left_offset", 0),
        right_offset=getattr(config, "right_offset", 0),
    ).start()
