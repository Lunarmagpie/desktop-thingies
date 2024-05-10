from desktop_thingies import Texture

objects = [
    Texture(texture="examples/reimu_fumo.png", scale=1 / 6),
    Texture(texture="examples/reimu_fumo.png", scale=1 / 5, displays=["DP-3"]),  # Display this fumo only on DP-3
]
