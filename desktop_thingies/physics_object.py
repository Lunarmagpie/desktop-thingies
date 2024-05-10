import dataclasses
from abc import ABC, abstractmethod

import gi
import pymunk

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
    displays: list[str | None] = dataclasses.field(kw_only=True, default_factory=list)
    """The displays this object should display on. ie. DP-3"""

    _physics_shape: pymunk.Shape | None = None
    _body: pymunk.Body | None = None

    def initiate(self):
        """inititate the physics object"""

    @abstractmethod
    def render_onto(self, snapshot: Gtk.Snapshot):
        """Render the object at 0,0 on the snapshot"""


@dataclasses.dataclass(kw_only=True)
class Texture(PhysicsObject):
    texture: str = dataclasses.field()
    """The path to a PNG image to use as the texture for this obejct"""
    scale: float = dataclasses.field(kw_only=True, default=1)
    """Amount to scale the image."""

    def initiate(self):
        self._gdk_texture = Gdk.Texture.new_from_filename(self.texture)

        radius = (
            min(self._gdk_texture.get_width(), self._gdk_texture.get_height())
            / SIMULATION_SCALE
            / 2
            * self.scale
        )
        self._physics_shape = pymunk.Circle(
            pymunk.Body(self.mass, pymunk.moment_for_circle(self.mass, 0, radius)),
            radius=radius,
        )

        self._body = self._physics_shape.body
        self._physics_shape.friction = self.friction
        self._physics_shape.elasticity = self.elasticity

    def render_onto(self, snapshot: Gtk.Snapshot):
        bounds = Graphene.Rect().init(
            -self._gdk_texture.get_width() / 2 * self.scale,
            -self._gdk_texture.get_height() / 2 * self.scale,
            self._gdk_texture.get_width() * self.scale,
            self._gdk_texture.get_height() * self.scale,
        )
        snapshot.append_scaled_texture(
            self._gdk_texture, Gsk.ScalingFilter.TRILINEAR, bounds
        )


@dataclasses.dataclass
class Circle(PhysicsObject):
    radius: int = dataclasses.field(kw_only=True)
    color: str = dataclasses.field(kw_only=True)

    def initiate(self):
        self._physics_shape = pymunk.Circle(
            pymunk.Body(self.mass, pymunk.moment_for_circle(self.mass, 0, self.radius)),
            radius=self.radius / SIMULATION_SCALE,
        )
        self._body = self._physics_shape.body
        self._gtk_color = Gtk.Color()
        self._gtk_color.parse(self.color)

    def render_onto(self, snapshot: Gtk.Snapshot):
        rect = Graphene.Rect().init(
            -self.radius * SIMULATION_SCALE,
            -self.radius * SIMULATION_SCALE,
            self.radius * 2 * SIMULATION_SCALE,
            self.radius * 2 * SIMULATION_SCALE,
        )

        rounded_rect = Gsk.RoundedRect()
        rounded_rect.init_from_rect(rect, radius=90)
        snapshot.push_rounded_clip(rounded_rect)
        snapshot.append_color(self.color, rect)
        snapshot.pop()


@dataclasses.dataclass
class Rectangle(PhysicsObject):
    width: int = dataclasses.field(kw_only=True)
    height: int = dataclasses.field(kw_only=True)
    color: str = dataclasses.field(kw_only=True)

    def initiate(self):
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
        self._gtk_color = Gtk.Color()
        self._gtk_color.parse(self.color)

    def render_onto(self, snapshot: Gtk.Snapshot):
        rect = Graphene.Rect().init(
            -self.width / 2 * SIMULATION_SCALE,
            -self.height / 2 * SIMULATION_SCALE,
            self.width * SIMULATION_SCALE,
            self.height * SIMULATION_SCALE,
        )
        snapshot.append_color(self.color, rect)
