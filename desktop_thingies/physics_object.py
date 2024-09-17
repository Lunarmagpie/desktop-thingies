import dataclasses
from abc import ABC, abstractmethod
import random

import gi
import pymunk
from PIL import Image

from desktop_thingies.constants import SIMULATION_SCALE
from gi.repository import Gdk, Graphene, Gsk, Gtk  # type: ignore


@dataclasses.dataclass
class PhysicsObject(ABC):
    mass: float = dataclasses.field(kw_only=True, default=1)
    """This mass of the object"""
    friction: float = dataclasses.field(kw_only=True, default=0.5)
    """The friction of the object"""
    elasticity: float = dataclasses.field(kw_only=True, default=0.85)
    """The elasticity of the object"""
    pickup_distance: float= dataclasses.field(kw_only=True, default=10)
    """How many pixels the mouse can be from the object when you try to pick it up."""

    _physics_shape: pymunk.Shape = dataclasses.field(default=None)  # type: ignore
    _body: pymunk.Body = dataclasses.field(default=None)  # type: ignore

    _last_velocity_x = 0
    _last_velocity_y = 0

    _strech_scale_x = 0
    _strech_scale_y = 0
    _strech_time = 0

    @abstractmethod
    def render_onto(self, snapshot: Gtk.Snapshot):
        """Render the object at 0,0 on the snapshot"""


@dataclasses.dataclass(kw_only=True)
class Texture(PhysicsObject):
    texture: str = dataclasses.field()
    """The path to a PNG image to use as the texture for this obejct"""
    scale: float = dataclasses.field(kw_only=True, default=1)
    """Amount to scale the image."""
    collision_scale: float = dataclasses.field(kw_only=True, default=1)
    """The size ofthe collison in comparision to the size of the image."""

    def __post_init__(self):
        texture_file = Image.open(self.texture)
        height, width = texture_file.size

        uniq = str(map(random.choice, ["abcdefghijklmnopqrztuvwxyz"] * 10))
        DEST = f"/tmp/{uniq}.png"

        texture_file = texture_file.resize((int(height * self.scale), int(width * self.scale)))
        texture_file.save(DEST)
        
        self._gdk_texture = Gdk.Texture.new_from_filename(DEST)

        radius = (
            min(self._gdk_texture.get_width(), self._gdk_texture.get_height())
            / SIMULATION_SCALE
            / 2
        )
        self._physics_shape = pymunk.Circle(
            pymunk.Body(self.mass, pymunk.moment_for_circle(self.mass, 0, radius * self.collision_scale)),
            radius=radius * self.collision_scale,
        )

        self._body = self._physics_shape.body
        self._physics_shape.friction = self.friction
        self._physics_shape.elasticity = self.elasticity

    def render_onto(self, snapshot: Gtk.Snapshot):
        bounds = Graphene.Rect().init(
            -self._gdk_texture.get_width() / 2,
            -self._gdk_texture.get_height() / 2,
            self._gdk_texture.get_width(),
            self._gdk_texture.get_height(),
        )
        snapshot.append_scaled_texture(
            self._gdk_texture, Gsk.ScalingFilter.TRILINEAR, bounds
        )


@dataclasses.dataclass
class Circle(PhysicsObject):
    radius: float = dataclasses.field(kw_only=True)
    color: str = dataclasses.field(kw_only=True, default="#000000")

    def __post_init__(self):
        self.radius /= SIMULATION_SCALE
        self._physics_shape = pymunk.Circle(
            pymunk.Body(self.mass, pymunk.moment_for_circle(self.mass, 0, self.radius / SIMULATION_SCALE)),
            radius=self.radius,
        )
        self._body = self._physics_shape.body
        self._gtk_color = Gdk.RGBA()
        self._gtk_color.parse(self.color)

    def render_onto(self, snapshot: Gtk.Snapshot):
        rect = Graphene.Rect().init(
            -self.radius * SIMULATION_SCALE,
            -self.radius * SIMULATION_SCALE,
            self.radius * 2 * SIMULATION_SCALE,
            self.radius * 2 * SIMULATION_SCALE,
        )

        rounded_rect = Gsk.RoundedRect()
        rounded_rect.init_from_rect(rect, radius=self.radius * SIMULATION_SCALE)
        snapshot.push_rounded_clip(rounded_rect)
        snapshot.append_color(self._gtk_color, rect)
        snapshot.pop()


@dataclasses.dataclass
class Rectangle(PhysicsObject):
    width: float = dataclasses.field(kw_only=True)
    height: float= dataclasses.field(kw_only=True)
    color: str = dataclasses.field(kw_only=True, default="#000000")

    def __post_init__(self):
        self.width /= SIMULATION_SCALE
        self.height /= SIMULATION_SCALE
        
        self._physics_shape = pymunk.Poly(
            pymunk.Body(
                self.mass, pymunk.moment_for_box(self.mass, (self.width, self.height))
            ),
            vertices=[
                (-self.width / 2, -self.height / 2),
                (self.width / 2, -self.height / 2),
                (self.width / 2, self.height / 2),
                (-self.width / 2, self.height / 2),
            ],
        )
        self._body = self._physics_shape.body
        self._gtk_color = Gdk.RGBA()
        self._gtk_color.parse(self.color)

    def render_onto(self, snapshot: Gtk.Snapshot):
        rect = Graphene.Rect().init(
            -self.width / 2 * SIMULATION_SCALE,
            -self.height / 2 * SIMULATION_SCALE,
            self.width * SIMULATION_SCALE,
            self.height * SIMULATION_SCALE,
        )
        snapshot.append_color(self._gtk_color, rect)
