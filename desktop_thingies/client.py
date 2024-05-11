import dataclasses
import random
import threading
import time
import math
from collections.abc import Callable
from copy import deepcopy

import gi
import pymunk

from desktop_thingies.constants import SIMULATION_SCALE
from desktop_thingies.physics_object import PhysicsObject

from gi.repository import Gdk, Graphene, Gtk, Gtk4LayerShell as LayerShell  # type: ignore

THEME = """
window.background {
   background: unset;
}  
"""


def add_box(space: pymunk.Space, p0: tuple[int, int], p1: tuple[int, int], d: int = 4):
    WALL_WIDTH = 50
    x0, y0 = p0
    x1, y1 = p1
    ps = [
        (x0 - WALL_WIDTH, y0 - WALL_WIDTH),
        (x1 + WALL_WIDTH, y0 - WALL_WIDTH),
        (x1 + WALL_WIDTH, y1 + WALL_WIDTH),
        (x0 - WALL_WIDTH, y1 + WALL_WIDTH),
    ]
    for i in range(4):
        segment = pymunk.Segment(space.static_body, ps[i], ps[(i + 1) % 4], WALL_WIDTH)
        segment.elasticity = 0.5
        segment.friction = 0.5
        space.add(segment)


class Canvas(Gtk.Widget):
    def __init__(self, draw_func: Callable[[Gtk.Snapshot], None] | None = None) -> None:
        draw_func = draw_func
        super().__init__()

        self.set_hexpand(True)
        self.set_vexpand(True)

    def do_snapshot(self, snapshot: Gtk.Snapshot):
        assert self.draw_func, "Draw func should not be None."
        self.draw_func(snapshot)


@dataclasses.dataclass
class PhysicsSpace:
    monitor: Gdk.Monitor
    window: Gtk.Window
    canvas: Canvas
    physics_space: pymunk.Space
    physics_objects: list[PhysicsObject]

    holding_body: pymunk.Body | None = None

    mouse_position: tuple[int, int] = (0, 0)

    SCALE = 10
    CLICK_TOLERANCE = 1
    has_saved = False

    def _draw(self, snapshot: Gtk.Snapshot):
        for obj in self.physics_objects:
            angle = math.degrees(obj._body.angle)

            pos = obj._body.position
            snapshot.translate(
                Graphene.Point().init(
                    pos.x * SIMULATION_SCALE, pos.y * SIMULATION_SCALE
                )
            )
            snapshot.rotate(-angle)

            obj.render_onto(snapshot)

            snapshot.rotate(angle)
            snapshot.translate(
                Graphene.Point().init(
                    -pos.x * SIMULATION_SCALE, -pos.y * SIMULATION_SCALE
                )
            )

    def _on_mouse_click(self, gesture, data, x, y):
        if self.holding_body != None:
            return
        for obj in self.physics_space.shapes:
            if (
                obj.point_query((x / SIMULATION_SCALE, y / SIMULATION_SCALE)).distance
                <= self.CLICK_TOLERANCE
            ):
                self.holding_body = obj.body

    def _on_mouse_release(self, gesture, data, x, y):
        if self.holding_body:
            distance = (
                self.mouse_position[0] / SIMULATION_SCALE
                - self.holding_body.position[0],
                self.mouse_position[1] / SIMULATION_SCALE
                - self.holding_body.position[1],
            )
            self.holding_body.apply_impulse_at_world_point(
                (distance[0] * 50, distance[1] * 50), self.holding_body.position
            )
        self.holding_body = None

    def _on_mouse_move(self, motion, x, y):
        self.mouse_position = (x, y)

    @staticmethod
    def limit_velocity(body, gravity, damping, dt):
        max_velocity = 500
        max_angular_velocity = 1.5
        pymunk.Body.update_velocity(body, gravity, damping, dt)

        # No matter what apply friction
        body.velocity *= 0.99
        body.angular_velocity *= 0.99

        if body.velocity.length > max_velocity:
            body.velocity *= 0.8
        if body.velocity.length > max_velocity * 1.5:
            body.velocity = body.velocity * 0.5

        if abs(body.angular_velocity > max_angular_velocity):
            body.angular_velocity = body.angular_velocity * 0.8

    def update(self, step: float):
        if self.holding_body is not None:
            distance = (
                self.mouse_position[0] / SIMULATION_SCALE
                - self.holding_body.position[0],
                self.mouse_position[1] / SIMULATION_SCALE
                - self.holding_body.position[1],
            )
            self.holding_body.velocity = (0, 0)

            x, y = 0, 0
            if 0 <= self.mouse_position[0] <= self.monitor.get_geometry().width:
                x = distance[0] * 30
            if 0 <= self.mouse_position[1] <= self.monitor.get_geometry().height:
                y = distance[1] * 30
            self.holding_body.apply_impulse_at_world_point(
                (x, y), self.holding_body.position
            )

        self.physics_space.step(step)
        self.canvas.queue_draw()

    def setup_window(self):
        geometry = self.monitor.get_geometry()

        LayerShell.init_for_window(self.window)
        LayerShell.set_layer(self.window, LayerShell.Layer.BACKGROUND)
        LayerShell.set_keyboard_mode(self.window, LayerShell.KeyboardMode.NONE)
        LayerShell.set_monitor(self.window, self.monitor)

        self.window.set_default_size(geometry.width, geometry.height)

        self.window.set_child(self.canvas)

        # Mouse events
        click_event = Gtk.GestureClick().new()
        click_event.connect("pressed", self._on_mouse_click)
        click_event.connect("released", self._on_mouse_release)
        self.window.add_controller(click_event)

        move_event = Gtk.EventControllerMotion.new()
        move_event.connect("motion", self._on_mouse_move)
        self.window.add_controller(move_event)

        pass

    def setup_drawing_area(self):
        self.canvas.draw_func = self._draw
        pass

    def setup_physics_space(self):
        geometry = self.monitor.get_geometry()
        self.physics_space.gravity = (0, 0)
        self.physics_space

        for shape in self.physics_objects:
            shape.initiate()

            self.physics_space.add(shape._body)
            self.physics_space.add(shape._physics_shape)

            shape._body.position = pymunk.Vec2d(
                random.randrange(0, geometry.width / SIMULATION_SCALE),
                random.randrange(0, geometry.height / SIMULATION_SCALE),
            )
            shape._body.angle = random.random() * math.pi * 2
            shape._body.velocity_func = self.limit_velocity
            self.physics_space.reindex_shapes_for_body(shape._body)

        add_box(
            self.physics_space,
            (0, 0),
            (geometry.width / SIMULATION_SCALE, geometry.height / SIMULATION_SCALE),
        )


@dataclasses.dataclass
class Client:
    objects: list[PhysicsObject]
    target_framerate: int | None = None

    _spaces: list[PhysicsSpace] = dataclasses.field(default_factory=list)

    def physics_update(self):
        while True:
            # Techinically this puts the framerate a little below the target,
            # but pymunk seems to segfault if you call the function again before the
            # step time is over.
            STEP = 1.0 / (self.target_framerate or 60)

            for space in self._spaces:
                space.update(STEP)

            time.sleep(STEP * 1.01)

    def on_activate(self, app):
        provider = Gtk.CssProvider()
        provider.load_from_data(THEME, len(THEME))

        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        for monitor in display.get_monitors():
            # These are the objects that will be intereacted with by the engines
            physics_space = pymunk.Space(threaded=False)

            objects = []
            for object in self.objects:
                if object.displays and monitor.get_connector() not in object.displays:
                    continue
                objects += [deepcopy(object)]
            if not objects:
                # Do not create the window if there are no objects to put on it.
                continue

            canvas = Canvas()
            window = Gtk.ApplicationWindow()

            space = PhysicsSpace(monitor, window, canvas, physics_space, objects)
            self._spaces += [space]

            space.setup_window()
            space.setup_drawing_area()
            space.setup_physics_space()

            app.add_window(window)
            window.present()

    def start(self):
        self.space = pymunk.Space()

        app = Gtk.Application()
        app.connect("activate", self.on_activate)

        threads = [
            threading.Thread(target=self.physics_update, args=[]),
            threading.Thread(target=app.run, args=[]),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
