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

from gi.repository import Gdk, Gsk, Graphene, Gtk, GLib, Gtk4LayerShell as LayerShell  # type: ignore

THEME = """
window.background {
   background: unset;
}  
"""


class Vec2(typing.NamedTuple):
    width: int
    height: int


def add_box(
    space: pymunk.Space,
    friction: float,
    elasticity: float,
    p0: tuple[int, int],
    p1: tuple[int, int],
    d: int = 4,
):
    WALL_WIDTH = 1000
    WALL_OFFSET = 0
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
        segment.elasticity = friction
        segment.friction = elasticity
        space.add(segment)


def clamp(n: float, max: float):
    if n < 0:
        if n < -max:
            return -max
    if n > max:
        return max
    return n

def rotate(point, angle):
    return (
        math.cos(angle) * point[0] - math.sin(angle) * point[1],
        math.sin(angle) * point[0] + math.cos(angle) * point[1]
    )


class Canvas(Gtk.Widget):
    def __init__(self, draw_func: Callable[[Gtk.Snapshot], None] | None = None) -> None:
        draw_func = draw_func
        super().__init__()

        self.set_hexpand(True)
        self.set_vexpand(True)

    def do_snapshot(self, snapshot: Gtk.Snapshot):
        assert self.draw_func, "Draw func should not be None."
        self.draw_func(snapshot)


@dataclasses.dataclass(kw_only=True)
class PhysicsSpace:
    monitor: Gdk.Monitor
    window: Gtk.Window
    canvas: Canvas
    target_framerate: int | None

    physics_space: pymunk.Space
    physics_objects: list[PhysicsObject]
    gravity: tuple[float, float] = (0, 0)
    wall_friction: float = 0.5
    wall_elasticity: float = 0.5
    top_offset: int = 0
    bottom_offset: int = 0
    left_offset: int = 0
    right_offset: int = 0


    holding_body: pymunk.Body | None = None
    is_initialized: bool = False

    mouse_position: tuple[int, int] = (0, 0)
    sim_lock: threading.Semaphore = dataclasses.field(
        default_factory=threading.BoundedSemaphore
    )

    SCALE = 10
    has_saved = False

    sim_sleep = False
    sim_frame = 0

    def __post_init__(self):
        geometry = self.monitor.get_geometry()
        self.geometry = Vec2(
            geometry.width,
            geometry.height,
        )

    def _draw(self, snapshot: Gtk.Snapshot):
        self.sim_lock.acquire()
        for obj in self.physics_objects:
            snapshot.save()

            angle = math.degrees(obj._body.angle)

            x_strech = max(1, (abs(obj._body.velocity.x) - 70) / 1000 * .8 + 1)
            y_strech = max(1, (abs(obj._body.velocity.y) - 70) / 1000 * .8 + 1)
            x_strech -= (y_strech - 1) / 2
            y_strech -= (x_strech - 1) / 2

            x_diff = abs(obj._body.velocity.x - obj._last_velocity_x)
            y_diff = abs(obj._body.velocity.y - obj._last_velocity_y)

            STRECH_TIME = 4
            if (obj._strech_time > 0):
                x_strech = 1 - (1 - obj._strech_scale_x) * (obj._strech_time / STRECH_TIME)
                y_strech = 1 - (1 - obj._strech_scale_y) * (obj._strech_time / STRECH_TIME)
            elif (
                (abs(obj._last_velocity_x) > 0.1 and math.copysign(1, obj._body.velocity.x / obj._last_velocity_x) == -1 or abs(obj._body.velocity.x - obj._last_velocity_x) > 10)
                or (abs(obj._last_velocity_y) > 0.1 and math.copysign(1, obj._body.velocity.y / obj._last_velocity_y) == -1  or abs(obj._body.velocity.y - obj._last_velocity_y) > 10)
            ):
                vector_angle = math.cos(obj._last_velocity_y / (obj._last_velocity_x or 0.00001))
                velocity = x_diff + y_diff

                strech = max(0.8, 1 - (max(velocity  - 10, 1) / 800) ** 1.8)
                x_strech, y_strech = rotate((strech, strech), vector_angle)
                

                obj._strech_scale_x = max(x_strech, .4)
                obj._strech_scale_y = max(y_strech, .4)
                obj._strech_time = STRECH_TIME + 1

            if x_strech > 1.5:
                x_strech = 1.5
            if y_strech > 1.5:
                y_strech = 1.5

            if (self.holding_body == obj._body):
                x_strech = 1.05
                y_strech = 1.05

            if abs(obj._body.angular_velocity) > 10:
                y_strech += abs(obj._body.angular_velocity) / 500

            pos = obj._body.position

            snapshot.translate(
                Graphene.Point().init(
                    pos.x * SIMULATION_SCALE, pos.y * SIMULATION_SCALE
                )
            )
            snapshot.transform(Gsk.Transform.new().scale(x_strech, y_strech))

            snapshot.rotate(angle)

            obj.render_onto(snapshot)

            snapshot.restore()

            obj._last_velocity_x = obj._body.velocity.x
            obj._last_velocity_y = obj._body.velocity.y
            obj._strech_time -= 1

        self.sim_lock.release()

    def check_hovered_object(self, x, y) -> pymunk.Body | None:
        if self.holding_body:
            self.canvas.set_cursor_from_name("grabbing")
            return self.holding_body
        self.sim_lock.acquire()
        for obj in self.physics_objects:
            if (
                obj._physics_shape.point_query(
                    (x / SIMULATION_SCALE, y / SIMULATION_SCALE)
                ).distance
                <= obj.pickup_distance / SIMULATION_SCALE
            ):
                self.canvas.set_cursor_from_name("grab")
                self.sim_lock.release()
                return obj
        self.canvas.set_cursor_from_name("default")
        self.sim_lock.release()
        return None

    def _on_mouse_click(self, gesture, data, x, y):
        self.sim_sleep = False
        if self.holding_body != None:
            return
        self.holding_body = getattr(self.check_hovered_object(x, y), "_body", None)
        if self.holding_body:
            self.canvas.set_cursor_from_name("grabbing")
            frame_clock = self.window.get_frame_clock()
            frame_clock.begin_updating()

    def _on_mouse_release(self, gesture, data, x, y):
        if self.holding_body != None:
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
            self.check_hovered_object(x, y)

    def _on_mouse_move(self, motion, x, y):
        SMALLER_BOUND = 5
        if x < SMALLER_BOUND + self.left_offset:
            x = SMALLER_BOUND + self.left_offset
        if x > self.geometry.width - SMALLER_BOUND - self.right_offset:
            x = self.geometry.width - SMALLER_BOUND - self.right_offset
        if y < SMALLER_BOUND + self.bottom_offset:
            y = SMALLER_BOUND + self.bottom_offset
        if y > self.geometry.height - SMALLER_BOUND - self.top_offset:
            y = self.geometry.height - SMALLER_BOUND - self.top_offset
        self.mouse_position = (x, y)
        self.check_hovered_object(x, y)

    def _on_scroll(self, event, x, y):
        if self.holding_body:
            self.sim_lock.acquire()
            self.holding_body.angular_velocity += y
            self.physics_space.reindex_shapes_for_body(self.holding_body)
            self.sim_lock.release()

    def _on_after_paint(self, _):
        STEP = 1 / (self.target_framerate or 60)

        frame_clock = self.window.get_frame_clock()

        self.update(STEP)

        # If the window is sleeping we don't need to update the sim or visuals.
        # GTK will send another update tick once we intereact with an object which
        # will cause the sim to update.
        if not self.sim_sleep:
            time.sleep(STEP)
            # Schedule a new frame now that this one is over.
            frame_clock.begin_updating()

    def limit_velocity(self, body, gravity, damping, dt):
        max_velocity = 500
        max_angular_velocity = 15
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

        if body is not self.holding_body:
            if abs(body.angular_velocity) > max_angular_velocity:
                body.angular_velocity = body.angular_velocity * 0.8

        if body is self.holding_body:
            if abs(body.angular_velocity) >= 50:
                body.angular_velocity = math.copysign(30, body.angular_velocity)

        # Finally, velocity close to 0 should be set to 0
        if body.velocity.length < 0.25:
            body.velocity = (0, 0)
        if abs(body.angular_velocity) < 0.001:
            body.angular_velocity = 0

    def update(self, step: float):
        if not self.is_initialized:
            return

        if self.holding_body is not None:
            self.sim_sleep = False
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

        if not self.sim_sleep:
            self.sim_frame += 1
            self.sim_lock.acquire()
            self.physics_space.step(step)
            self.canvas.queue_draw()

            if self.sim_frame > 200:
                self.sim_sleep = True
            for object in self.physics_objects:
                if (
                    object._body.velocity.length != 0
                    or object._body.angular_velocity != 0
                ):
                    self.sim_sleep = False
            self.sim_lock.release()

    def setup_window(self):
        LayerShell.init_for_window(self.window)
        LayerShell.set_layer(self.window, LayerShell.Layer.BOTTOM)
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
        scroll_event = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll_event.connect("scroll", self._on_scroll)
        self.window.add_controller(scroll_event)

        self.window.present()

        self.window.get_frame_clock().connect("after_paint", self._on_after_paint)

    def setup_drawing_area(self):
        self.canvas.draw_func = self._draw

    def setup_physics_space(self):
        self.physics_space.gravity = self.gravity

        for shape in self.physics_objects:
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
            self.wall_elasticity,
            self.wall_friction,
            (self.left_offset / SIMULATION_SCALE, self.top_offset / SIMULATION_SCALE),
            (
                (self.geometry.width - self.right_offset) / SIMULATION_SCALE,
                (self.geometry.height - self.bottom_offset)  / SIMULATION_SCALE,
            ),
        )

        self.is_initialized = True


@dataclasses.dataclass(kw_only=True)
class Client:
    objects: list[PhysicsObject]
    monitor: str | None = None
    target_framerate: int | None = None
    gravity: tuple[float, float] = (0, 0)
    wall_friction: float = 0.5
    wall_elasticity: float = 0.5
    top_offset: int = 0
    bottom_offset: int = 0
    left_offset: int = 0
    right_offset: int = 0

    _spaces: list[PhysicsSpace] = dataclasses.field(default_factory=list)

    def on_activate(self, app):
        provider = Gtk.CssProvider()
        provider.load_from_data(THEME, len(THEME))

        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        for monitor in display.get_monitors():
            if self.monitor and monitor.get_connector() != self.monitor:
                continue

            # These are the objects that will be intereacted with by the engines
            physics_space = pymunk.Space(threaded=False)

            canvas = Canvas()
            window = Gtk.ApplicationWindow()

            space = PhysicsSpace(
                monitor=monitor,
                window=window,
                canvas=canvas,
                target_framerate=self.target_framerate,
                physics_space=physics_space,
                physics_objects=self.objects,
                gravity=self.gravity,
                wall_friction=self.wall_friction,
                wall_elasticity=self.wall_elasticity,
                top_offset=self.top_offset,
                bottom_offset=self.bottom_offset,
                left_offset=self.left_offset,
                right_offset=self.right_offset,
            )
            self._spaces += [space]

            space.setup_drawing_area()
            space.setup_window()
            space.setup_physics_space()

            app.add_window(window)
            # We only run one window to prevent bugs (i am lazy af)
            break
        else:
            raise Exception(f"Monitor {self.monitor} not found")

    def start(self):
        app = Gtk.Application()
        app.connect("activate", self.on_activate)
        app.run()
