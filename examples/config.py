from desktop_thingies import Texture

# The display this program should show up on, optional
display = "DP-3"

# The target framerate, optional
framerate = 60

# The vertical and horizontal gravity for the stage.
gravity = (0, 0)

# The physics objects to display.
objects = [
    Texture(texture="examples/reimu_fumo.png", scale=1 / 6),
    Texture(texture="examples/reimu_fumo.png", scale=1 / 5),
]
