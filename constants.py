from enum import Enum


class Tool(Enum):
    PLACE = 0
    ERASE = 1
    FILL = 2
    SELECT = 3
    PASTE = 4
    EYEDROPPER = 5
    BRUSH = 6


class Layer(Enum):
    BACKGROUND = 0
    MIDGROUND = 1


class TileConnection(Enum):
    NONE = 0
    TOP = 1
    MIDDLE = 2
    BOTTOM = 3
    SINGLE = 4
