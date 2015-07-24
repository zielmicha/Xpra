# coding=utf8
# This file is part of Xpra.
# Copyright (C) 2012-2014 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import os
import win32api         #@UnresolvedImport
import win32con         #@UnresolvedImport
import win32ui          #@UnresolvedImport
import win32gui         #@UnresolvedImport
import win32process     #@UnresolvedImport

from xpra.log import Logger
from xpra.util import AdHocStruct
log = Logger("shadow", "win32")
shapelog = Logger("shape")

from xpra.os_util import StringIOClass
from xpra.server.gtk_server_base import GTKServerBase
from xpra.server.shadow_server_base import ShadowServerBase, RootWindowModel
from xpra.platform.win32.keyboard_config import KeyboardConfig, fake_key
from xpra.codecs.image_wrapper import ImageWrapper

NOEVENT = object()
BUTTON_EVENTS = {
                 #(button,up-or-down)  : win-event-name
                 (1, True)  : (win32con.MOUSEEVENTF_LEFTDOWN,   0),
                 (1, False) : (win32con.MOUSEEVENTF_LEFTUP,     0),
                 (2, True)  : (win32con.MOUSEEVENTF_MIDDLEDOWN, 0),
                 (2, False) : (win32con.MOUSEEVENTF_MIDDLEUP,   0),
                 (3, True)  : (win32con.MOUSEEVENTF_RIGHTDOWN,  0),
                 (3, False) : (win32con.MOUSEEVENTF_RIGHTUP,    0),
                 (4, True)  : (win32con.MOUSEEVENTF_WHEEL,      win32con.WHEEL_DELTA),
                 (4, False) : NOEVENT,
                 (5, True)  : (win32con.MOUSEEVENTF_WHEEL,      -win32con.WHEEL_DELTA),
                 (5, False) : NOEVENT,
                 }

SEAMLESS = os.environ.get("XPRA_WIN32_SEAMLESS", "0")=="1"


class Win32RootWindowModel(RootWindowModel):

    def __init__(self, root):
        RootWindowModel.__init__(self, root)
        if SEAMLESS:
            self.property_names.append("shape")
            self.dynamic_property_names.append("shape")
            self.rectangles = self.get_shape_rectangles(logit=True)
            self.shape_notify = []

    def refresh_shape(self):
        rectangles = self.get_shape_rectangles()
        if rectangles==self.rectangles:
            return  #unchanged
        self.rectangles = rectangles
        shapelog("refresh_shape() sending notify for updated rectangles: %s", rectangles)
        #notify listeners:
        pspec = AdHocStruct()
        pspec.name = "shape"
        for cb, args in self.shape_notify:
            shapelog("refresh_shape() notifying: %s", cb)
            try:
                cb(self, pspec, *args)
            except:
                shapelog.error("error in shape notify callback %s", cb, exc_info=True)

    def connect(self, signal, cb, *args):
        if signal=="notify::shape":
            self.shape_notify.append((cb, args))
        else:
            RootWindowModel.connect(self, signal, cb, *args)

    def get_shape_rectangles(self, logit=False):
        #get the list of windows
        l = log
        if logit or os.environ.get("XPRA_SHAPE_DEBUG", "0")=="1":
            l = shapelog
        taskbar = win32gui.FindWindow("Shell_TrayWnd", None)
        l("taskbar window=%#x", taskbar)
        ourpid = os.getpid()
        l("our pid=%i", ourpid)
        def enum_windows_cb(hwnd, rects):
            if not win32gui.IsWindowVisible(hwnd):
                l("skipped invisible window %#x", hwnd)
                return True
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid==ourpid:
                l("skipped our own window %#x", hwnd)
                return True
            #skipping IsWindowEnabled check
            window_title = win32gui.GetWindowText(hwnd)
            l("get_shape_rectangles() found window '%s' with pid=%s", window_title, pid)
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            if right<0 or bottom<0:
                l("skipped offscreen window at %ix%i", right, bottom)
                return True
            if hwnd==taskbar:
                l("skipped taskbar")
                return True
            #dirty way:
            if window_title=='Program Manager':
                return True
            #this should be the proper way using GetTitleBarInfo (but does not seem to work)
            #import ctypes
            #from ctypes.windll.user32 import GetTitleBarInfo        #@UnresolvedImport
            #from ctypes.wintypes import (DWORD, RECT)
            #class TITLEBARINFO(ctypes.Structure):
            #    pass
            #TITLEBARINFO._fields_ = [
            #    ('cbSize', DWORD),
            #    ('rcTitleBar', RECT),
            #    ('rgstate', DWORD * 6),
            #]
            #ti = TITLEBARINFO()
            #ti.cbSize = ctypes.sizeof(ti)
            #GetTitleBarInfo(hwnd, ctypes.byref(ti))
            #if ti.rgstate[0] & win32con.STATE_SYSTEM_INVISIBLE:
            #    log("skipped system invisible window")
            #    return True
            w = right-left
            h = bottom-top 
            l("shape(%s - %#x)=%s", window_title, hwnd, (left, top, w, h))
            if w<=0 and h<=0:
                l("skipped invalid window size: %ix%i", w, h)
                return True
            if left==-32000 and top==-32000:
                #there must be a better way of skipping those - I haven't found it
                l("skipped special window")
                return True
            #now clip rectangle:
            if left<0:
                left = 0
                w = right
            if top<0:
                top = 0
                h = bottom
            rects.append((left, top, w, h))
            return True
        rectangles = []
        win32gui.EnumWindows(enum_windows_cb, rectangles)
        l("get_shape_rectangles()=%s", rectangles)
        return sorted(rectangles)

    def get_property(self, prop):
        if prop=="shape":
            assert SEAMLESS
            shape = {"Bounding.rectangles" : self.rectangles}
            #provide clip rectangle? (based on workspace area?)
            return shape
        return RootWindowModel.get_property(self, prop)


    def get_root_window_size(self):
        w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        return w, h


    def get_image(self, x, y, width, height, logger=None):
        desktop_wnd = win32gui.GetDesktopWindow()
        dx = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        dy = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
        dw = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        dh = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        #clamp rectangle requested to the virtual desktop size:
        if x<dx:
            width -= x-dx
            x = dx
        if y<dy:
            height -= y-dy
            y = dy
        if width>dw:
            width = dw
        if height>dh:
            height = dh
        ddc, cdc, bitmap = None, None, None
        try:
            ddc = win32gui.GetWindowDC(desktop_wnd)
            assert ddc, "cannot get a drawing context from the desktop window %s" % desktop_wnd
            cdc = win32ui.CreateDCFromHandle(ddc)
            assert cdc, "cannot get a compatible drawing context from the desktop drawing context %s" % ddc
            memdc = cdc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(cdc, width, height)
            memdc.SelectObject(bitmap)
            memdc.BitBlt((0, 0), (width, height), cdc, (x, y), win32con.SRCCOPY)
            pixels = bitmap.GetBitmapBits(True)
        finally:
            pass
        assert pixels, "no pixels returned from GetBitmapBits"
        return ImageWrapper(0, 0, width, height, pixels, "BGRX", 24, width*4, planes=ImageWrapper.PACKED, thread_safe=True)

    def take_screenshot(self):
        from PIL import Image
        x = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        y = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
        w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)        
        h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        image = self.get_image(x, y, w, h)
        assert image.get_width()==w and image.get_height()==h
        assert image.get_pixel_format()=="BGRX"
        img = Image.frombuffer("RGB", (w, h), image.get_pixels(), "raw", "BGRX", 0, 1)
        out = StringIOClass()
        img.save(out, format="PNG")
        screenshot = (img.width, img.height, "png", img.width*3, out.getvalue())
        out.close()
        return screenshot


class ShadowServer(ShadowServerBase, GTKServerBase):

    def __init__(self):
        #TODO: root should be a wrapper for the win32 system metrics bits?
        #(or even not bother passing root to ShadowServerBase?
        import gtk.gdk
        ShadowServerBase.__init__(self, gtk.gdk.get_default_root_window())
        GTKServerBase.__init__(self)
        self.keycodes = {}

    def makeRootWindowModel(self):
        return Win32RootWindowModel(self.root)

    def refresh(self):
        v = ShadowServerBase.refresh(self)
        if v and SEAMLESS:
            self.root_window_model.refresh_shape()
        log("refresh()=%s", v)
        return v

    def _process_mouse_common(self, proto, wid, pointer, modifiers):
        #adjust pointer position for offset in client:
        x, y = pointer
        wx, wy = self.mapped_at[:2]
        rx, ry = x-wx, y-wy
        win32api.SetCursorPos((rx, ry))

    def get_keyboard_config(self, props):
        return KeyboardConfig()

    def fake_key(self, keycode, press):
        fake_key(keycode, press)

    def _process_button_action(self, proto, packet):
        wid, button, pressed, pointer, modifiers = packet[1:6]
        self._process_mouse_common(proto, wid, pointer, modifiers)
        self._server_sources.get(proto).user_event()
        event = BUTTON_EVENTS.get((button, pressed))
        if event is None:
            log.warn("no matching event found for button=%s, pressed=%s", button, pressed)
            return
        elif event is NOEVENT:
            return
        x, y = pointer
        dwFlags, dwData = event
        win32api.mouse_event(dwFlags, x, y, dwData, 0)

    def make_hello(self, source):
        capabilities = GTKServerBase.make_hello(self, source)
        capabilities["shadow"] = True
        capabilities["server_type"] = "Python/gtk2/win32-shadow"
        return capabilities

    def get_info(self, proto):
        info = GTKServerBase.get_info(self, proto)
        info["features.shadow"] = True
        info["server.type"] = "Python/gtk2/win32-shadow"
        return info


def main():
    from xpra.platform import init, clean
    try:
        init("Shadow-Test", "Shadow Server Screen Capture Test")
        rwm = Win32RootWindowModel(None)
        pngdata = rwm.take_screenshot()
        FILENAME = "screenshot.png"
        with open(FILENAME , "wb") as f:
            f.write(pngdata[4])
        print("saved screenshot as %s" % FILENAME)
    finally:
        #this will wait for input on win32:
        clean()

if __name__ == "__main__":
    main()
