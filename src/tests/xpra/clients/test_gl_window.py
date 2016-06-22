#!/usr/bin/env python
# This file is part of Xpra.
# Copyright (C) 2012, 2013 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import binascii
import math
import struct
from xpra.log import Logger
log = Logger()

import glib

from xpra.util import typedict
from xpra.client.gl.gtk2.gl_client_window import GLClientWindow
from tests.xpra.clients.fake_gtk_client import FakeGTKClient, gtk_main
from xpra.codecs.loader import load_codecs

load_codecs(encoders=False, decoders=True, csc=False)


def paint_window(window):
    W, H = window.get_size()
    img_data = binascii.unhexlify("89504e470d0a1a0a0000000d494844520000010000000100010300000066bc3a2500000003504c54"
                                  "45b5d0d0630416ea0000001f494441546881edc1010d000000c2a0f74f6d0e37a000000000000000"
                                  "00be0d210000019a60e1d50000000049454e44ae426082")
    window.draw_region((W-256)//2, (H-256)//2, 256, 256, "png", img_data, W*4, 0, typedict(), [])

def paint_rect(window, x=200, y=200, w=32, h=32, color=0x80808080, options=typedict()):
    print("paint_rect%s" % ((x, y, w, h),))
    c = struct.pack("@I", color)
    img_data = c*w*h
    window.draw_region(x, y, w, h, "rgb32", img_data, w*4, 0, typedict(options), [])

def paint_and_scroll(window, ydelta=10, color=0xA0A0A0A):
    print("paint_and_scroll(%i, %#x)" % (ydelta, color))
    W, H = window.get_size()
    if ydelta>0:
        #scroll down, repaint the top:
        scrolls = (0, 0, W, H-ydelta, ydelta),
        window.draw_region(0, 0, W, H, "scroll", scrolls, W*4, 0, typedict({"flush" : 1}), [])
        paint_rect(window, 0, 0, W, ydelta, color)
    else:
        #scroll up, repaint the bottom:
        scrolls = (0, -ydelta, W, H+ydelta, ydelta),
        window.draw_region(0, 0, W, H, "scroll", scrolls, W*4, 0, typedict({"flush" : 1}), [])
        paint_rect(window, 0, H-ydelta, W, -ydelta, color)

def split_scroll(window, i=1):
    W, H = window.get_size()
    scrolls = [
               (0,      i,      W,      H//2,       -i),
               (0,      H//2,   W,      H//2-i,     i),
               ]
    window.draw_region(0, 0, W, H, "scroll", scrolls, W*4, 0, typedict({}), [])


def main():
    W = 640
    H = 480
    client = FakeGTKClient()
    window = GLClientWindow(client, None, 1, 10, 10, W, H, W, H, typedict({}), False, typedict({}), 0, None)
    window.show()
    glib.timeout_add(0, paint_rect, window, 0, 0, W, H, 0xFFFFFFFF)
    glib.timeout_add(0, paint_window, window)
    for i in range(4):
        glib.timeout_add(500, paint_rect, window, W//4*i + W//8, 100, 32, 32, 0x30*i)
    for i in range(50):
        glib.timeout_add(1000+i*20, paint_rect, window, int(W//3+math.sin(i/10.0)*128), int(H//2-32+math.cos(i/10.0)*64))
        glib.timeout_add(1000+i*20, paint_and_scroll, window, -1)
        glib.timeout_add(2000+i*20, paint_rect, window, int(W//3*2-math.sin(i/10.0)*128), int(H//2-16-math.cos(i/10.0)*64), 32, 32, 0x10)
        glib.timeout_add(2000+i*20, paint_and_scroll, window, +1)
    for i in range(200):
        glib.timeout_add(4000+i*20, split_scroll, window, max(1, i//50))
        glib.timeout_add(4000+i*20, paint_rect, window, 0, H//2-1, W, 2, i+i*0x100) 
        
    try:
        gtk_main()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()