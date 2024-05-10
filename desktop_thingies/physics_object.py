# A base class for implementing desktop widget
from ctypes import ArgumentError
import dataclasses
from typing import Protocol
from abc import ABC, abstractmethod, abstractproperty
import pymunk

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Gsk, Graphene  # type: ignore


class Collision(ABC):
    @abstractmethod
    def get_shape(self) -> pymunk.Shape:
        pass

    @abstractmethod
    def render_bounds(self, snapshot: Gtk.Snapshot, color: Gdk.RGBA):
        pass


@dataclasses.dataclass
class Circle(Collision):
    mass: float
    radius: float

    def get_shape(self) -> pymunk.Shape:
        return pymunk.Circle(
            pymunk.Body(self.mass, pymunk.moment_for_circle(self.mass, 0, self.radius)),
            radius=self.radius,
        )

    def render_bounds(self, snapshot: Gtk.Snapshot, color: Gdk.RGBA):
        rect = Graphene.Rect().init(
            -self.radius * 10,
            -self.radius * 10,
            self.radius * 2 * 10,
            self.radius * 2 * 10,
        )

        rounded_rect = Gsk.RoundedRect()
        rounded_rect.init_from_rect(rect, radius=90)

        snapshot.push_rounded_clip(rounded_rect)
        snapshot.append_color(color, rect)
        snapshot.pop()  # remove the clip


@dataclasses.dataclass
class Rectangle(Collision):
    mass: float
    width: float
    height: float

    def get_shape(self) -> pymunk.Shape:
        return pymunk.Poly(
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

    def render_bounds(self, snapshot: Gtk.Snapshot, color: Gdk.RGBA):
        rect = Graphene.Rect().init(
            -self.width / 2 * 10,
            -self.height / 2 * 10,
            self.width * 10,
            self.height * 10,
        )
        snapshot.append_color(color, rect)


@dataclasses.dataclass
class PhysicsObject(ABC):
    mass: float = dataclasses.field(kw_only=True, default=1)
    friction: float = dataclasses.field(kw_only=True, default=.5)
    elasticity: float = dataclasses.field(kw_only=True, default=.85)
    displays: list[str | None] = dataclasses.field(kw_only=True, default_factory=list)

    physics_shape: pymunk.Shape | None = None
    body: pymunk.Body | None = None

    def initiate(self):
        """inititate the physics object"""

    @abstractmethod
    def render_onto(self, snapshot: Gtk.Snapshot):
        """Render the object at 0,0 on the snapshot"""


@dataclasses.dataclass(kw_only=True)
class Texture(PhysicsObject):
    texture: str = dataclasses.field()
    scale: float = dataclasses.field(kw_only=True, default=1)

    def initiate(self):
        self._gdk_texture = Gdk.Texture.new_from_filename(self.texture)

        self.shape = Circle(
            self.mass,
            self._gdk_texture.get_width() * self.scale / 10 / 2,
        )

        self.physics_shape = self.shape.get_shape()
        self.body = self.physics_shape.body
        self.physics_shape.friction = self.friction
        self.physics_shape.elasticity = self.elasticity

    def render_onto(self, snapshot: Gtk.Snapshot):
        """Render the object at 0,0 on the snapsho"""

        bounds = Graphene.Rect().init(
            -self._gdk_texture.get_width() / 2 * self.scale,
            -self._gdk_texture.get_height() / 2 * self.scale,
            self._gdk_texture.get_width() * self.scale,
            self._gdk_texture.get_height() * self.scale,
        )  # See warning below
        snapshot.append_scaled_texture(
            self._gdk_texture, Gsk.ScalingFilter.TRILINEAR, bounds
        )
