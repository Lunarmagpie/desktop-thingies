import dataclasses
import random
import typing
import threading
import time
import math
from collections.abc import Callable
from copy import deepcopy

import gi
import pymunk

from desktop_thingies.constants import SIMULATION_SCALE
from desktop_thingies.physics_object import PhysicsObject

from gi.repository import Gdk, Graphene, Gtk, GLib, Gtk4LayerShell as LayerShell  # type: ignore

THEME = """
window.background {
   background: unset;
}  
"""


class Vec2(typing.NamedTuple):
    width: int
    height: int


def add_box(space: pymunk.Space, p0: tuple[int, int], p1: tuple[int, int], d: int = 4):
    WALL_WIDTH = 1000
    WALL_OFFSET = 2
    x0, y0 = p0
    x1, y1 = p1
    ps = [
        (x0 - WALL_WIDTH - WALL_OFFSET, y0 - WALL_WIDTH - WALL_OFFSET),
        (x1 + WALL_WIDTH + WALL_OFFSET, y0 - WALL_WIDTH - WALL_OFFSET),
        (x1 + WALL_WIDTH + WALL_OFFSET, y1 + WALL_WIDTH + WALL_OFFSET),
        (x0 - WALL_WIDTH - WALL_OFFSET, y1 + WALL_WIDTH + WALL_OFFSET),
    ]
    for i in range(4):
        segment = pymunk.Segment(space.static_body, ps[i], ps[(i + 1) % 4], WALL_WIDTH)
        segment.elasticity = 0.5
        segment.friction = 0.5
        space.add(segment)


def clamp(n: float, max: float):
    if n < 0:
        if n < -max:
            return -max
    if n > max:
        return max
    return n


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
    is_initialized: bool = False

    mouse_position: tuple[int, int] = (0, 0)
    sim_lock: threading.Semaphore = dataclasses.field(default_factory=threading.BoundedSemaphore)

    SCALE = 10
    CLICK_TOLERANCE = 1
    has_saved = False

    sim_sleep = False
    sim_can_sleep = True

    def __post_init__(self):
        geometry = self.monitor.get_geometry()
        self.geometry = Vec2(
            geometry.width,
            geometry.height,
        )

    def _draw(self, snapshot: Gtk.Snapshot):
        self.sim_lock.acquire()
        for obj in self.physics_objects:
            assert obj._body
            snapshot.save()
            angle = math.degrees(obj._body.angle)

            pos = obj._body.position
            snapshot.translate(
                Graphene.Point().init(
                    pos.x * SIMULATION_SCALE, pos.y * SIMULATION_SCALE
                )
            )
            snapshot.rotate(angle)
            obj.render_onto(snapshot)

            snapshot.restore()
        self.sim_lock.release()

    def _on_mouse_click(self, gesture, data, x, y):
        self.sim_sleep = False
        self.sim_can_sleep = False
        if self.holding_body != None:
            return
        self.sim_lock.acquire()
        for obj in self.physics_space.shapes:
            if (
                obj.point_query((x / SIMULATION_SCALE, y / SIMULATION_SCALE)).distance
                <= self.CLICK_TOLERANCE
            ):
                self.holding_body = obj.body
        self.sim_lock.release()

    def _on_mouse_release(self, gesture, data, x, y):
        self.sim_can_sleep = True
        if self.holding_body:
            self.sim_lock.acquire()
            distance = (
                clamp(
                    self.mouse_position[0] / SIMULATION_SCALE
                    - self.holding_body.position[0],
                    1000,
                ),
                clamp(
                    self.mouse_position[1] / SIMULATION_SCALE
                    - self.holding_body.position[1],
                    1000,
                ),
            )

            self.holding_body.apply_impulse_at_world_point(
                (distance[0] * (1 / 0.3) * 4, distance[1] * (1 / 0.3) * 4),
                self.holding_body.position,
            )
            self.sim_lock.release()

            self.holding_body = None

    def _on_mouse_move(self, motion, x, y):
        SMALLER_BOUND = 5
        if x < SMALLER_BOUND:
            x = SMALLER_BOUND
        if x > self.geometry.width - SMALLER_BOUND:
            x = self.geometry.width - SMALLER_BOUND
        if y < SMALLER_BOUND:
            y = SMALLER_BOUND
        if y > self.geometry.height - SMALLER_BOUND:
            y = self.geometry.height - SMALLER_BOUND
        self.mouse_position = (x, y)

    def _on_after_paint(self, user_data):
        if not self.sim_sleep:
            self.canvas.queue_draw()
        self.window.get_frame_clock().request_phase(Gdk.FrameClockPhase.PAINT)
    
    def limit_velocity(self, body, gravity, damping, dt):
        max_velocity = 500
        max_angular_velocity = 1.5
        pymunk.Body.update_velocity(body, gravity, damping, dt)

        # No matter what apply friction
        body.velocity *= 0.99
        body.angular_velocity *= 0.99

        if self.holding_body == body:
            body.velocity *= 0.3

        if body.velocity.length > max_velocity:
            body.velocity *= 0.9
        if body.velocity.length > max_velocity * 1.5:
            body.velocity = body.velocity * 0.5

        if abs(body.angular_velocity > max_angular_velocity):
            body.angular_velocity = body.angular_velocity * 0.8

        # Finally, velocity close to 0 should be set to 0
        if body.velocity.length < 0.25:
            body.velocity = (0, 0)
        if body.angular_velocity < 0.001:
            body.angular_velocity = 0

    def update(self, step: float):
        if not self.is_initialized:
            return

        if self.holding_body is not None:
            distance = (
                self.mouse_position[0] / SIMULATION_SCALE
                - self.holding_body.position[0],
                self.mouse_position[1] / SIMULATION_SCALE
                - self.holding_body.position[1],
            )

            x = distance[0] * (1 / 0.3) * 2
            y = distance[1] * (1 / 0.3) * 2

            self.sim_lock.acquire()
            self.holding_body.apply_impulse_at_world_point(
                (x, y),
                self.holding_body.position,
            )
            self.sim_lock.release()

        # TODO: If nothing is happening, we want to skip updating the sim
        is_anything_moving = False

        for object in self.physics_objects:
            assert object._body
            if object._body.velocity.length != 0 or object._body.angular_velocity != 0:
                is_anything_moving = True

        if not is_anything_moving and self.sim_can_sleep:
            self.sim_sleep = True

        if not self.sim_sleep:
            self.physics_space.step(step)

    def setup_window(self):
        LayerShell.init_for_window(self.window)
        LayerShell.set_layer(self.window, LayerShell.Layer.BACKGROUND)
        LayerShell.set_keyboard_mode(self.window, LayerShell.KeyboardMode.NONE)
        LayerShell.set_monitor(self.window, self.monitor)

        self.window.set_default_size(self.geometry.width, self.geometry.height)
        self.window.set_child(self.canvas)

        # Mouse events
        click_event = Gtk.GestureClick().new()
        click_event.connect("pressed", self._on_mouse_click)
        click_event.connect("released", self._on_mouse_release)
        self.window.add_controller(click_event)

        move_event = Gtk.EventControllerMotion.new()
        move_event.connect("motion", self._on_mouse_move)
        
        self.window.add_controller(move_event)

        self.window.present()

        frame_clock = self.window.get_frame_clock()
        frame_clock.connect("after_paint", self._on_after_paint)

    def setup_drawing_area(self):
        self.canvas.draw_func = self._draw

    def setup_physics_space(self):
        self.physics_space.gravity = (0, 0)
        self.physics_space

        for shape in self.physics_objects:
            shape.initiate()

            assert shape._body
            assert shape._physics_shape

            self.physics_space.add(shape._body)
            self.physics_space.add(shape._physics_shape)

            shape._body.position = pymunk.Vec2d(
                random.randrange(0, self.geometry.width / SIMULATION_SCALE),
                random.randrange(0, self.geometry.height / SIMULATION_SCALE),
            )
            shape._body.angle = random.random() * math.pi * 2
            shape._body.velocity_func = self.limit_velocity
            self.physics_space.reindex_shapes_for_body(shape._body)

        add_box(
            self.physics_space,
            (0, 0),
            (
                self.geometry.width / SIMULATION_SCALE,
                self.geometry.height / SIMULATION_SCALE,
            ),
        )

        self.is_initialized = True


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
            STEP = 0.02

            for space in self._spaces:
                space.update(STEP)

            time.sleep(STEP)

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

            space.setup_drawing_area()
            space.setup_window()
            space.setup_physics_space()

            app.add_window(window)


    def start(self):
        self.space = pymunk.Space()

        app = Gtk.Application()
        app.connect("activate", self.on_activate)
        GLib.Thread.new("physics", self.physics_update)
        app.run()
