# This file is part of Xpra.
# Copyright (C) 2010 Nathaniel Smith <njs@pobox.com>
# Copyright (C) 2011-2014 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import struct
from xpra.log import Logger
log = Logger("posix")
eventlog = Logger("events", "posix")

from xpra.gtk_common.gobject_compat import get_xid, is_gtk3
from xpra.gtk_common.error import trap, XError

device_bell = None

def get_native_notifier_classes():
    ncs = []
    try:
        from xpra.client.notifications.dbus_notifier import DBUS_Notifier_factory
        ncs.append(DBUS_Notifier_factory)
    except Exception as e:
        log("cannot load dbus notifier: %s", e)
    try:
        from xpra.client.notifications.pynotify_notifier import PyNotify_Notifier
        ncs.append(PyNotify_Notifier)
    except Exception as e:
        log("cannot load pynotify notifier: %s", e)
    return ncs

def get_native_tray_classes():
    try:
        from xpra.platform.xposix.appindicator_tray import AppindicatorTray, can_use_appindicator
        if can_use_appindicator():
            return [AppindicatorTray]
    except Exception as e:
        log("cannot load appindicator tray: %s", e)
    return []

def get_native_system_tray_classes():
    #appindicator can be used for both
    return get_native_tray_classes()


#we duplicate some of the code found in gtk_x11.prop ...
#which is still better than having dependencies on that GTK2 code
def _get_X11_root_property(name, req_type):
    try:
        from xpra.x11.bindings.window_bindings import X11WindowBindings, PropertyError #@UnresolvedImport
        window_bindings = X11WindowBindings()
        root = window_bindings.getDefaultRootWindow()
        try:
            prop = trap.call_synced(window_bindings.XGetWindowProperty, root, name, req_type)
            log("_get_X11_root_property(%s, %s)=%s, len=%s", name, req_type, type(prop), len(prop))
            return prop
        except PropertyError as e:
            log("_get_X11_root_property(%s, %s): %s", name, req_type, e)
    except Exception as e:
        log.warn("failed to get workarea: %s", e)
    return None


def _get_xsettings():
    try:
        from xpra.x11.bindings.window_bindings import X11WindowBindings #@UnresolvedImport
        window_bindings = X11WindowBindings()
        selection = "_XSETTINGS_S0"
        owner = window_bindings.XGetSelectionOwner(selection)
        if not owner:
            return None
        XSETTINGS = "_XSETTINGS_SETTINGS"
        data = window_bindings.XGetWindowProperty(owner, XSETTINGS, XSETTINGS)
        if not data:
            return None
        from xpra.x11.xsettings_prop import get_settings
        return get_settings(None, data)
    except Exception as e:
        log("_get_xsettings error: %s", e)
    return None


def get_antialias_info():
    info = {}
    try:
        from xpra.x11.xsettings_prop import XSettingsTypeInteger, XSettingsTypeString
        v = _get_xsettings()
        if v:
            _, values = v
            for setting_type, prop_name, value, _ in values:
                #-1 means default, so we just don't specify it
                if setting_type==XSettingsTypeInteger and value>=0:
                    if prop_name=="Xft/Antialias":
                        info["enabled"] = bool(value)
                    elif prop_name=="Xft/Hinting":
                        info["hinting"] = bool(value)
                if setting_type==XSettingsTypeString:
                    if prop_name=="Xft/HintStyle":
                        info["hintstyle"] = value
                        #win32 API uses numerical values:
                        #(this is my best guess at translating the X11 names)
                        contrast = {"hintnone"      : 0,
                                    "hintslight"    : 1000,
                                    "hintmedium"    : 1600,
                                    "hintfull"      : 2200}.get(value, -1)
                        if contrast>=0:
                            info["contrast"] = contrast
                    elif prop_name=="Xft/RGBA":
                        info["orientation"] = str(value).upper()
    except Exception as e:
        log.warn("failed to get antialias info from xsettings: %s", e)
    return info


def get_current_desktop():
    try:
        d = _get_X11_root_property("_NET_CURRENT_DESKTOP", "CARDINAL")
        v = struct.unpack("=I", d)[0]
        log("get_current_desktop()=%s", v)
        return v
    except Exception as e:
        log.warn("failed to get current desktop: %s", e)
    return -1

def get_workarea():
    try:
        d = get_current_desktop()
        if d<0:
            return None
        workarea = _get_X11_root_property("_NET_WORKAREA", "CARDINAL")
        log("get_workarea()=%s, len=%s", type(workarea), len(workarea))
        #workarea comes as a list of 4 CARDINAL dimensions (x,y,w,h), one for each desktop
        if len(workarea)<(d+1)*4*4:
            log.warn("get_workarea() invalid _NET_WORKAREA value")
        else:
            cur_workarea = workarea[d*4*4:(d+1)*4*4]
            v = struct.unpack("=IIII", cur_workarea)
            log("get_workarea()=%s", v)
            return v
    except Exception as e:
        log.warn("failed to get workarea: %s", e)
    return None


def get_vrefresh():
    try:
        from xpra.x11.bindings.randr_bindings import RandRBindings      #@UnresolvedImport
        randr = RandRBindings()
        return randr.get_vrefresh()
    except Exception as e:
        log.warn("failed to get VREFRESH: %s", e)
        return -1


def _get_xsettings_int(name, default_value):
    s = _get_xsettings()
    if not s:
        return default_value
    from xpra.x11.xsettings_prop import XSettingsTypeInteger
    _, values = s
    for setting_type, prop_name, value, _ in values:
        if setting_type==XSettingsTypeInteger and prop_name==name:
            return value
    return default_value

def get_double_click_time():
    return _get_xsettings_int("Net/DoubleClickTime", -1)

def get_double_click_distance():
    v = _get_xsettings_int("Net/DoubleClickDistance", -1)
    return v, v


def system_bell(window, device, percent, pitch, duration, bell_class, bell_id, bell_name):
    global device_bell
    if device_bell is False:
        #failed already
        return False
    def x11_bell():
        global device_bell
        if device_bell is None:
            #try to load it:
            from xpra.x11.bindings.keyboard_bindings import X11KeyboardBindings       #@UnresolvedImport
            device_bell = X11KeyboardBindings().device_bell
        device_bell(get_xid(window), device, bell_class, bell_id, percent, bell_name)
    try:
        trap.call_synced(x11_bell)
        return  True
    except XError as e:
        log.error("error using device_bell: %s, switching native X11 bell support off", e)
        device_bell = False
        return False


def get_info():
    from xpra.platform.gui import get_info_base
    i = get_info_base()
    s = _get_xsettings()
    if s:
        serial, values = s
        i["xsettings.serial"] = serial
        for _,name,value,_ in values:
            i["xsettings.%s" % name] = value
    return i


class ClientExtras(object):
    def __init__(self, client, opts):
        self.client = client
        self._xsettings_watcher = None
        self._root_props_watcher = None
        self.system_bus = None
        self.upower_resuming_match = None
        self.upower_sleeping_match = None
        self.login1_match = None
        if client.xsettings_enabled:
            self.setup_xprops()
        self.setup_dbus_signals()

    def cleanup(self):
        log("cleanup() xsettings_watcher=%s, root_props_watcher=%s", self._xsettings_watcher, self._root_props_watcher)
        if self._xsettings_watcher:
            self._xsettings_watcher.cleanup()
            self._xsettings_watcher = None
        if self._root_props_watcher:
            self._root_props_watcher.cleanup()
            self._root_props_watcher = None
        if self.system_bus:
            bus = self.system_bus
            log("cleanup() system bus=%s, matches: %s", bus, (self.upower_resuming_match, self.upower_sleeping_match, self.login1_match))
            self.system_bus = None
            if self.upower_resuming_match:
                bus._clean_up_signal_match(self.upower_resuming_match)
            if self.upower_sleeping_match:
                bus._clean_up_signal_match(self.upower_sleeping_match)
            if self.login1_match:
                bus._clean_up_signal_match(self.login1_match)

    def resuming_callback(self, *args):
        eventlog("resuming_callback%s", args)
        self.client.resume()

    def sleeping_callback(self, *args):
        eventlog("sleeping_callback%s", args)
        self.client.suspend()


    def setup_dbus_signals(self):
        try:
            from xpra.x11.dbus_common import init_system_bus
            bus = init_system_bus()
            self.system_bus = bus
            log("setup_dbus_signals() system bus=%s", bus)
        except Exception as e:
            log.warn("dbus setup error: %s", e)
            return

        #the UPower signals:
        try:
            bus_name    = 'org.freedesktop.UPower'
            log("bus has owner(%s)=%s", bus_name, bus.name_has_owner(bus_name))
            iface_name  = 'org.freedesktop.UPower'
            self.upower_resuming_match = bus.add_signal_receiver(self.resuming_callback, 'Resuming', iface_name, bus_name)
            self.upower_sleeping_match = bus.add_signal_receiver(self.sleeping_callback, 'Sleeping', iface_name, bus_name)
            eventlog("listening for 'Resuming' and 'Sleeping' signals on %s", iface_name)
        except Exception as e:
            eventlog("failed to setup UPower event listener: %s", e)

        #the "logind" signals:
        try:
            bus_name    = 'org.freedesktop.login1'
            log("bus has owner(%s)=%s", bus_name, bus.name_has_owner(bus_name))
            def sleep_event_handler(suspend):
                if suspend:
                    self.sleeping_callback()
                else:
                    self.resuming_callback()
            iface_name  = 'org.freedesktop.login1.Manager'
            self.login1_match = bus.add_signal_receiver(sleep_event_handler, 'PrepareForSleep', iface_name, bus_name)
            eventlog("listening for 'PrepareForSleep' signal on %s", iface_name)
        except Exception as e:
            eventlog("failed to setup login1 event listener: %s", e)

    def setup_xprops(self):
        #wait for handshake to complete:
        self.client.connect("handshake-complete", self.do_setup_xprops)

    def do_setup_xprops(self, *args):
        log("do_setup_xprops(%s)", args)
        if is_gtk3():
            log("x11 root properties and XSETTINGS are not supported yet with GTK3")
            return
        ROOT_PROPS = ["RESOURCE_MANAGER", "_NET_WORKAREA", "_NET_CURRENT_DESKTOP"]
        try:
            from xpra.x11.xsettings import XSettingsWatcher
            from xpra.x11.xroot_props import XRootPropWatcher
            if self._xsettings_watcher is None:
                self._xsettings_watcher = XSettingsWatcher()
                self._xsettings_watcher.connect("xsettings-changed", self._handle_xsettings_changed)
                self._handle_xsettings_changed()
            if self._root_props_watcher is None:
                self._root_props_watcher = XRootPropWatcher(ROOT_PROPS)
                self._root_props_watcher.connect("root-prop-changed", self._handle_root_prop_changed)
                #ensure we get the initial value:
                self._root_props_watcher.do_notify("RESOURCE_MANAGER")
        except ImportError as e:
            log.error("failed to load X11 properties/settings bindings: %s - root window properties will not be propagated", e)

    def _handle_xsettings_changed(self, *args):
        try:
            settings = self._xsettings_watcher.get_settings()
        except:
            log.error("failed to get XSETTINGS", exc_info=True)
            return
        log("xsettings_changed new value=%s", settings)
        if settings is not None:
            self.client.send("server-settings", {"xsettings-blob": settings})

    def _handle_root_prop_changed(self, obj, prop):
        log("root_prop_changed(%s, %s)", obj, prop)
        if prop=="RESOURCE_MANAGER":
            if not self.client.xsettings_tuple:
                log.warn("xsettings tuple format not supported, update ignored")
                return
            import gtk.gdk
            root = gtk.gdk.get_default_root_window()
            from xpra.x11.gtk_x11.prop import prop_get
            value = prop_get(root, "RESOURCE_MANAGER", "latin1", ignore_errors=True)
            if value is not None:
                self.client.send("server-settings", {"resource-manager" : value.encode("utf-8")})
        elif prop=="_NET_WORKAREA":
            self.client.screen_size_changed("from %s event" % self._root_props_watcher)
        elif prop=="_NET_CURRENT_DESKTOP":
            self.client.workspace_changed("from %s event" % self._root_props_watcher)
        else:
            log.error("unknown property %s", prop)
