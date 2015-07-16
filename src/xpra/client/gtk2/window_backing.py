# This file is part of Xpra.
# Copyright (C) 2008 Nathaniel Smith <njs@pobox.com>
# Copyright (C) 2012-2014 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

from gtk import gdk
import os

from xpra.log import Logger
log = Logger("paint")

from xpra.client.gtk_base.gtk_window_backing_base import GTKWindowBacking
from xpra.client.window_backing_base import fire_paint_callbacks
from xpra.codecs.loader import has_codec

USE_PIL = os.environ.get("XPRA_USE_PIL", "1")=="1"


"""
This is the gtk2 version.
(works much better than gtk3!)
Superclass for PixmapBacking and GLBacking
"""
class GTK2WindowBacking(GTKWindowBacking):

    def init(self, w, h):
        raise Exception("override me!")


    def paint_image(self, coding, img_data, x, y, width, height, options, callbacks):
        """ can be called from any thread """
        if USE_PIL and has_codec("dec_pillow"):
            return GTKWindowBacking.paint_image(self, coding, img_data, x, y, width, height, options, callbacks)
        #gdk needs UI thread:
        self.idle_add(self.paint_pixbuf_gdk, coding, img_data, x, y, width, height, options, callbacks)
        return  False

    def do_draw_region(self, x, y, width, height, coding, img_data, rowstride, options, callbacks):
        """ called as last resort when PIL is not available"""
        self.idle_add(self.paint_pixbuf_gdk, coding, img_data, x, y, width, height, options, callbacks)


    def paint_pixbuf_gdk(self, coding, img_data, x, y, width, height, options, callbacks):
        """ must be called from UI thread """
        if coding.startswith("png"):
            coding = "png"
        else:
            assert coding=="jpeg"
        loader = gdk.PixbufLoader(coding)
        loader.write(img_data, len(img_data))
        loader.close()
        pixbuf = loader.get_pixbuf()
        if not pixbuf:
            log.error("failed %s pixbuf=%s data len=%s" % (coding, pixbuf, len(img_data)))
            fire_paint_callbacks(callbacks, False)
            return  False
        raw_data = pixbuf.get_pixels()
        rowstride = pixbuf.get_rowstride()
        img_data = self.process_delta(raw_data, width, height, rowstride, options)
        n = pixbuf.get_n_channels()
        if n==3:
            self.do_paint_rgb24(img_data, x, y, width, height, rowstride, options, callbacks)
        else:
            assert n==4, "invalid number of channels: %s" % n
            self.do_paint_rgb32(img_data, x, y, width, height, rowstride, options, callbacks)
        return False
