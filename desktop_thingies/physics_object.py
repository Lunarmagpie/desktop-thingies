# A base class for implementing desktop widget
import dataclasses
from typing import Protocol
from abc import ABC, abstractmethod, abstractproperty
import pymunk

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Gsk, Graphene  # type: ignore


class Shape(ABC):
    @abstractmethod
    def get_shape(self) -> pymunk.Shape:
        pass

    @abstractmethod
    def render_bounds(self, snapshot: Gtk.Snapshot, color: Gdk.RGBA):
        pass

@dataclasses.dataclass
class Circle(Shape):
    mass: float
    radius: float

    def get_shape(self) -> pymunk.Shape:
        return pymunk.Circle(
            pymunk.Body(self.mass, pymunk.moment_for_circle(self.mass, 0, self.radius)),
            radius=self.radius,
        )

    def render_bounds(self, snapshot: Gtk.Snapshot, color: Gdk.RGBA):
        rect = Graphene.Rect().init(-self.radius/2 * 10, -self.radius/2 * 10, self.radius * 10, self.radius * 10)
        
        rounded_rect = Gsk.RoundedRect()
        rounded_rect.init_from_rect(rect, radius=90)
        
        snapshot.push_rounded_clip(rounded_rect)
        snapshot.append_color(color, rect)
        snapshot.pop()   # remove the clip

class Rectangle(Shape):
    mass: float
    width: float
    height: float

    def get_shape(self) -> pymunk.Shape:
        return pymunk.Poly(
            pymunk.Body(self.mass, pymunk.moment_for_box(self.mass, (self.width, self.height))),
            vertices=[
                (-self.width/2, -self.height/2),
                (self.width/2, -self.height/2),
                (self.width/2, self.height/2),
                (-self.width/2, self.height/2),
            ]
        )

    def render_bounds(self, snapshot: Gtk.Snapshot, color: Gdk.RGBA):
        rect = Graphene.Rect().init(-self.width/2 * 10, -self.height/2 * 10, self.width * 10, self.height * 10)
        snapshot.append_color(color, rect)

@dataclasses.dataclass
class PhysicsObject:
    shape: Shape

    friction = 0.5
    elasticity = 0.85

    texture: str | None = None
    color: str | None = None
    
    physics_shape: pymunk.Shape | None = None
    
    def __post_init__(self):
        self.physics_shape = self.shape.get_shape()
        self.body = self.physics_shape.body
        self.physics_shape.friction = self.friction
        self.physics_shape.elasticity = self.elasticity

    def render_onto(self, snapshot: Gtk.Snapshot):
        """Render the object at 0,0 on the snapsho"""
        if self.texture is None:
            assert self.color, "Must have texture or color"
            color = Gdk.RGBA()
            color.parse("#ABCDEF")

            self.shape.render_bounds(snapshot, color)

