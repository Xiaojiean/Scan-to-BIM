# Copyright (c) Open-MMLab. All rights reserved.
from enum import Enum
import random
import numpy as np

from mmcv.utils import is_str

COLOR_MAP_2D = {'wall': 'lime', 'door': 'red', 'window':'blue', 'room': 'green'}
COLOR_MAP_3D = {'wall': 'gray', 'beam':'brown', 'column':'blue', 'door':'cyan',  'window':'yellow',  'floor':'silver', 'ceiling':'navy', 'room':'green'}

class OLDColor(Enum):
    """An enum that defines common colors.

    Contains red, green, blue, cyan, yellow, magenta, white and black.
    """
    red = (0, 0, 255)
    green = (0, 255, 0)
    blue = (255, 0, 0)
    cyan = (255, 255, 0)
    yellow = (0, 255, 255)
    magenta = (255, 0, 255)
    white = (255, 255, 255)
    black = (0, 0, 0)

class Color_RGB(Enum):
    """An enum that defines common colors.

    Contains red, green, blue, cyan, yellow, magenta, white and black.
    """
    red   = (255,0,0)
    green = (0,128,0)
    lime =  (0,255,0)
    blue  =	(0,0,255)
    cyan  = (0,255,255)
    yellow= (255,255,0)
    magenta=(255,0,255)
    maroon= (128,0,0)
    purple= (128,0,128)
    navy  = (0,0,128)
    gray  = (128,128,128)
    brown = (165, 42, 42)
    silver = (192,192,192)

    olive = (128,128,0)
    teal = (0,128,128)
    orange = (255,165,0)
    gold = (255,215,0)
    yellow_green = (154,205,50)
    spring_green = (0,255,127)
    pink = 	(255,192,203)
    chocolate =  (210,105,30)
    peru = (205,133,63)
    hot_pink = (255,105,180)

    black = (0,0,0)
    white = (255,255,255)

ColorList = [e.name for e in Color_RGB][:-2] * 10
ColorValues = [e.value for e in Color_RGB] * 10
ColorValuesNp = np.array(ColorValues).astype(np.uint8)
NumColors = len(ColorList)

def _color(c, RGB=False):
  col = Color_RGB[c].value
  if RGB:
    return col
  else:
    return (col[2], col[1], col[0])

def get_random_color():
  # except black and white
  i = random.randint(0, NumColors)
  return ColorValues[i]

def _label2color(labels):
  colors = ['red', 'lime', 'blue',    'cyan', 'purple',   'gray','yellow',  'magenta', 'navy', 'green', ]
  #         'wall', 'beam', 'column', 'door', 'window', 'ceiling', 'floor'
  colors = ['gray', 'brown', 'blue', 'cyan', 'yellow', 'silver', 'silver', 'navy',
            'magenta', 'purple', 'green', 'olive', 'teal', 'orange', 'gold',
            'yellow_green', 'spring_green', 'pink', 'chocolate', 'peru', 'hot_pink']
  colors = colors + colors * 5
  n = len(colors)
  color_strs = [colors[ int(k%n) ] for k in labels]
  color_values = [color_val(c) for c in color_strs]
  #color_values = np.array(color_values)
  return color_values

def color_val(color):
    """Convert various input to color tuples.

    Args:
        color (:obj:`Color`/str/tuple/int/ndarray): Color inputs

    Returns:
        tuple[int]: A tuple of 3 integers indicating BGR channels.
    """
    if is_str(color):
        return _color(color)
    elif isinstance(color, tuple):
        assert len(color) == 3
        for channel in color:
            assert channel >= 0 and channel <= 255
        return color
    elif isinstance(color, int):
        assert color >= 0 and color <= 255
        return color, color, color
    elif isinstance(color, np.ndarray):
        assert color.ndim == 1 and color.size == 3
        assert np.all((color >= 0) & (color <= 255))
        color = color.astype(np.uint8)
        return tuple(color)
    else:
        raise TypeError('Invalid type for color: {}'.format(type(color)))

COLOR_MAP_RGB = (
    (241, 255, 82),
    (102, 168, 226),
    (0, 255, 0),
    (113, 143, 65),
    (89, 173, 163),
    (254, 158, 137),
    (190, 123, 75),
    (100, 22, 116),
    (0, 18, 141),
    (84, 84, 84),
    (85, 116, 127),
    (255, 31, 33),
    (228, 228, 228),
    (0, 255, 0),
    (70, 145, 150),
    (237, 239, 94),
)
IGNORE_COLOR = (0, 0, 0)

def label2color(labels):
  labels = labels.astype(np.int32).tolist()
  colors= [COLOR_MAP_RGB[i] for i in labels ]
  return colors
