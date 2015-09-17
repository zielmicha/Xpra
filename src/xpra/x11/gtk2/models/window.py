# This file is part of Xpra.
# Copyright (C) 2008, 2009 Nathaniel Smith <njs@pobox.com>
# Copyright (C) 2011-2014 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.


import gtk
import cairo

from xpra.gtk_common.gobject_util import one_arg_signal, non_none_list_accumulator
from xpra.gtk_common.error import XError
from xpra.x11.gtk_x11.send_wm import send_wm_take_focus
from xpra.x11.gtk_x11.prop import prop_set, prop_get, MotifWMHints
from xpra.x11.bindings.window_bindings import X11WindowBindings #@UnresolvedImport
from xpra.x11.gtk2.models import Unmanageable, MAX_WINDOW_SIZE
from xpra.x11.gtk2.models.base import BaseWindowModel, constants
from xpra.x11.gtk2.models.core import sanestr, gobject, xswallow, xsync
from xpra.x11.gtk2.gdk_bindings import (
                add_event_receiver,                         #@UnresolvedImport
                remove_event_receiver,                      #@UnresolvedImport
                get_display_for,                            #@UnresolvedImport
                calc_constrained_size,                      #@UnresolvedImport
               )

from xpra.log import Logger
log = Logger("x11", "window")
workspacelog = Logger("x11", "window", "workspace")
shapelog = Logger("x11", "window", "shape")
grablog = Logger("x11", "window", "grab")
metalog = Logger("x11", "window", "metadata")
iconlog = Logger("x11", "window", "icon")
focuslog = Logger("x11", "window", "focus")
geomlog = Logger("x11", "window", "geometry")


X11Window = X11WindowBindings()

IconicState = constants["IconicState"]
NormalState = constants["NormalState"]

CWX             = constants["CWX"]
CWY             = constants["CWY"]
CWWidth         = constants["CWWidth"]
CWHeight        = constants["CWHeight"]
CWBorderWidth   = constants["CWBorderWidth"]
CWSibling       = constants["CWSibling"]
CWStackMode     = constants["CWStackMode"]
CONFIGURE_GEOMETRY_MASK = CWX | CWY | CWWidth | CWHeight
CW_MASK_TO_NAME = {
                   CWX              : "X",
                   CWY              : "Y",
                   CWWidth          : "Width",
                   CWHeight         : "Height",
                   CWBorderWidth    : "BorderWidth",
                   CWSibling        : "Sibling",
                   CWStackMode      : "StackMode",
                   CWBorderWidth    : "BorderWidth",
                   }
def configure_bits(value_mask):
    return "|".join((v for k,v in CW_MASK_TO_NAME.items() if (k&value_mask)))


class WindowModel(BaseWindowModel):
    """This represents a managed client window.  It allows one to produce
    widgets that view that client window in various ways."""

    _NET_WM_ALLOWED_ACTIONS = ["_NET_WM_ACTION_%s" % x for x in (
        "CLOSE", "MOVE", "RESIZE", "FULLSCREEN",
        "MINIMIZE", "SHADE", "STICK",
        "MAXIMIZE_HORZ", "MAXIMIZE_VERT",
        "CHANGE_DESKTOP", "ABOVE", "BELOW")]

    __gproperties__ = dict(BaseWindowModel.__common_properties__)
    __gproperties__.update({
        "owner": (gobject.TYPE_PYOBJECT,
                  "Owner", "",
                  gobject.PARAM_READABLE),
        # Interesting properties of the client window, that will be
        # automatically kept up to date:
        "actual-size": (gobject.TYPE_PYOBJECT,
                        "Size of client window (actual (width,height))", "",
                        gobject.PARAM_READABLE),
        "user-friendly-size": (gobject.TYPE_PYOBJECT,
                               "Description of client window size for user", "",
                               gobject.PARAM_READABLE),
        "requested-position": (gobject.TYPE_PYOBJECT,
                               "Client-requested position on screen", "",
                               gobject.PARAM_READABLE),
        "requested-size": (gobject.TYPE_PYOBJECT,
                           "Client-requested size on screen", "",
                           gobject.PARAM_READABLE),
        # Toggling this property does not actually make the window iconified,
        # i.e. make it appear or disappear from the screen -- it merely
        # updates the various window manager properties that inform the world
        # whether or not the window is iconified.
        "iconic": (gobject.TYPE_BOOLEAN,
                   "ICCCM 'iconic' state -- any sort of 'not on desktop'.", "",
                   False,
                   gobject.PARAM_READWRITE),
        #from _NET_WM_ICON_NAME or WM_ICON_NAME
        "icon-title": (gobject.TYPE_PYOBJECT,
                       "Icon title (unicode or None)", "",
                       gobject.PARAM_READABLE),
        #from _NET_WM_ICON
        "icon": (gobject.TYPE_PYOBJECT,
                 "Icon (local Cairo surface)", "",
                 gobject.PARAM_READABLE),
        #from _NET_WM_ICON
        "icon-pixmap": (gobject.TYPE_PYOBJECT,
                        "Icon (server Pixmap)", "",
                        gobject.PARAM_READABLE),
        #from _MOTIF_WM_HINTS.decorations
        "decorations": (gobject.TYPE_BOOLEAN,
                       "Should the window decorations be shown", "",
                       True,
                       gobject.PARAM_READABLE),
        })
    __gsignals__ = dict(BaseWindowModel.__common_signals__)
    __gsignals__.update({
        "ownership-election"            : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_PYOBJECT, (), non_none_list_accumulator),
        "child-map-request-event"       : one_arg_signal,
        "child-configure-request-event" : one_arg_signal,
        "xpra-destroy-event"            : one_arg_signal,
        })

    _property_names         = BaseWindowModel._property_names + [
                              "icon-title", "icon", "decorations"]
    _dynamic_property_names = BaseWindowModel._dynamic_property_names + [
                              "icon-title", "icon", "decorations"]
    _initial_x11_properties = BaseWindowModel._initial_x11_properties + [
                              "WM_HINTS", "WM_NORMAL_HINTS", "_MOTIF_WM_HINTS",
                              "WM_ICON_NAME", "_NET_WM_ICON_NAME", "_NET_WM_ICON",
                              "_NET_WM_STRUT", "_NET_WM_STRUT_PARTIAL"]
    _MODELTYPE = "Window"

    def __init__(self, parking_window, client_window):
        """Register a new client window with the WM.

        Raises an Unmanageable exception if this window should not be
        managed, for whatever reason.  ATM, this mostly means that the window
        died somehow before we could do anything with it."""

        super(WindowModel, self).__init__(client_window)
        self.parking_window = parking_window
        self.corral_window = None
        #extra state attributes so we can unmanage() the window cleanly:
        self.in_save_set = False
        self.client_reparented = False
        self.last_unmap_serial = 0
        self.kill_count = 0

        self.call_setup()

    #########################################
    # Setup and teardown
    #########################################

    def setup(self):
        super(WindowModel, self).setup()

        x, y, w, h, _ = self.client_window.get_geometry()
        # We enable PROPERTY_CHANGE_MASK so that we can call
        # x11_get_server_time on this window.
        self.corral_window = gtk.gdk.Window(self.parking_window,
                                            x = x, y = y, width =w, height= h,
                                            window_type=gtk.gdk.WINDOW_CHILD,
                                            wclass=gtk.gdk.INPUT_OUTPUT,
                                            event_mask=gtk.gdk.PROPERTY_CHANGE_MASK,
                                            title = "CorralWindow-%#x" % self.xid)
        log("setup() corral_window=%#x", self.corral_window.xid)
        prop_set(self.corral_window, "_NET_WM_NAME", "utf8", u"Xpra-CorralWindow-%#x" % self.xid)
        X11Window.substructureRedirect(self.corral_window.xid)
        add_event_receiver(self.corral_window, self)

        # The child might already be mapped, in case we inherited it from
        # a previous window manager.  If so, we unmap it now, and save the
        # serial number of the request -- this way, when we get an
        # UnmapNotify later, we'll know that it's just from us unmapping
        # the window, not from the client withdrawing the window.
        if X11Window.is_mapped(self.xid):
            log("hiding inherited window")
            self.last_unmap_serial = X11Window.Unmap(self.xid)

        log("setup() adding to save set")
        X11Window.XAddToSaveSet(self.xid)
        self.in_save_set = True

        log("setup() reparenting")
        X11Window.Reparent(self.xid, self.corral_window.xid, 0, 0)
        self.client_reparented = True

        log("setup() geometry")
        w,h = X11Window.getGeometry(self.xid)[2:4]
        hints = self.get_property("size-hints")
        log("setup() hints=%s size=%ix%i", hints, w, h)
        nw, nh = calc_constrained_size(w, h, hints)[:2]
        if nw>=MAX_WINDOW_SIZE or nh>=MAX_WINDOW_SIZE:
            #we can't handle windows that big!
            raise Unmanageable("window constrained size is too large: %sx%s (from client geometry: %s,%s with size hints=%s)" % (nw, nh, w, h, hints))
        log("setup() resizing windows to %sx%s", nw, nh)
        self.corral_window.resize(nw, nh)
        self.client_window.resize(nw, nh)
        self.client_window.show_unraised()
        #this is here to trigger X11 errors if any are pending
        #or if the window is deleted already:
        self.client_window.get_geometry()
        self._internal_set_property("actual-size", (nw, nh))


    def _read_initial_X11_properties(self):
        metalog("read_initial_X11_properties() window")
        super(WindowModel, self)._read_initial_X11_properties()
        def pget(key, ptype):
            return self.prop_get(key, ptype, raise_xerrors=True)
        # WARNING: have to handle _NET_WM_STATE before we look at WM_HINTS;
        # WM_HINTS assumes that our "state" property is already set.  This is
        # because there are four ways a window can get its urgency
        # ("attention-requested") bit set:
        #   1) _NET_WM_STATE_DEMANDS_ATTENTION in the _initial_ state hints
        #   2) setting the bit WM_HINTS, at _any_ time
        #   3) sending a request to the root window to add
        #      _NET_WM_STATE_DEMANDS_ATTENTION to their state hints
        #   4) if we (the wm) decide they should be and set it
        # To implement this, we generally track the urgency bit via
        # _NET_WM_STATE (since that is under our sole control during normal
        # operation).  Then (1) is accomplished through the normal rule that
        # initial states are read off from the client, and (2) is accomplished
        # by having WM_HINTS affect _NET_WM_STATE.  But this means that
        # WM_HINTS and _NET_WM_STATE handling become intertangled.
        net_wm_state = self.get_property("state")
        assert net_wm_state is not None, "_NET_WM_STATE should have been read already"
        self._internal_set_property("modal", "_NET_WM_STATE_MODAL" in net_wm_state)
        geometry = X11Window.getGeometry(self.xid)
        self._internal_set_property("requested-position", (geometry[0], geometry[1]))
        self._internal_set_property("requested-size", (geometry[2], geometry[3]))
        self._internal_set_property("decorations", True)


    def do_unmanaged(self, wm_exiting):
        log("unmanaging window: %s (%s - %s)", self, self.corral_window, self.client_window)
        self._internal_set_property("owner", None)
        if self.corral_window:
            remove_event_receiver(self.corral_window, self)
            with xswallow:
                for prop in WindowModel.SCRUB_PROPERTIES:
                    X11Window.XDeleteProperty(self.xid, prop)
            if self.client_reparented:
                self.client_window.reparent(gtk.gdk.get_default_root_window(), 0, 0)
                self.client_reparented = False
            self.client_window.set_events(self.client_window_saved_events)
            #it is now safe to destroy the corral window:
            self.corral_window.destroy()
            self.corral_window = None
            # It is important to remove from our save set, even after
            # reparenting, because according to the X spec, windows that are
            # in our save set are always Mapped when we exit, *even if those
            # windows are no longer inferior to any of our windows!* (see
            # section 10. Connection Close).  This causes "ghost windows", see
            # bug #27:
            if self.in_save_set:
                with xswallow:
                    X11Window.XRemoveFromSaveSet(self.xid)
                self.in_save_set = False
            with xswallow:
                X11Window.sendConfigureNotify(self.xid)
            if wm_exiting:
                self.client_window.show_unraised()
        BaseWindowModel.do_unmanaged(self, wm_exiting)


    #########################################
    # Actions specific to WindowModel
    #########################################

    def raise_window(self):
        self.corral_window.raise_()

    def get_dimensions(self):
        return  self.get_property("actual-size")

    def unmap(self):
        with xsync:
            if X11Window.is_mapped(self.xid):
                self.last_unmap_serial = X11Window.Unmap(self.xid)
                log("client window %#x unmapped, serial=%s", self.xid, self.last_unmap_serial)

    def map(self):
        with xsync:
            if not X11Window.is_mapped(self.xid):
                X11Window.MapWindow(self.xid)
                log("client window %#x mapped", self.xid)


    #########################################
    # X11 Events
    #########################################

    def do_xpra_property_notify_event(self, event):
        if event.delivered_to is self.corral_window:
            return
        BaseWindowModel.do_xpra_property_notify_event(self, event)

    def do_child_map_request_event(self, event):
        # If we get a MapRequest then it might mean that someone tried to map
        # this window multiple times in quick succession, before we actually
        # mapped it (so that several MapRequests ended up queued up; FSF Emacs
        # 22.1.50.1 does this, at least).  It alternatively might mean that
        # the client is naughty and tried to map their window which is
        # currently not displayed.  In either case, we should just ignore the
        # request.
        log("do_child_map_request_event(%s)", event)

    def do_xpra_unmap_event(self, event):
        if event.delivered_to is self.corral_window or self.corral_window is None:
            return
        assert event.window is self.client_window
        # The client window got unmapped.  The question is, though, was that
        # because it was withdrawn/destroyed, or was it because we unmapped it
        # going into IconicState?
        #
        # Also, if we receive a *synthetic* UnmapNotify event, that always
        # means that the client has withdrawn the window (even if it was not
        # mapped in the first place) -- ICCCM section 4.1.4.
        log("do_xpra_unmap_event(%s) client window unmapped", event)
        if event.send_event or event.serial>self.last_unmap_serial:
            self.unmanage()

    def do_xpra_destroy_event(self, event):
        if event.delivered_to is self.corral_window or self.corral_window is None:
            return
        assert event.window is self.client_window
        super(WindowModel, self).do_xpra_destroy_event(event)


    #########################################
    # Hooks for WM
    #########################################

    def ownership_election(self):
        #returns True if we have updated the geometry
        candidates = self.emit("ownership-election")
        if candidates:
            rating, winner = sorted(candidates)[-1]
            if rating < 0:
                winner = None
        else:
            winner = None
        old_owner = self.get_property("owner")
        if old_owner is winner:
            return False
        if old_owner is not None:
            self.corral_window.hide()
            self.corral_window.reparent(self.parking_window, 0, 0)
        self._internal_set_property("owner", winner)
        if winner is not None:
            winner.take_window(self, self.corral_window)
            self._update_client_geometry()
            self.corral_window.show_unraised()
            return True
        with xswallow:
            X11Window.sendConfigureNotify(self.xid)
        return False

    def maybe_recalculate_geometry_for(self, maybe_owner):
        if maybe_owner and self.get_property("owner") is maybe_owner:
            self._update_client_geometry()

    def _update_client_geometry(self):
        owner = self.get_property("owner")
        geomlog("_update_client_geometry: owner=%s, setup_done=%s", owner, self._setup_done)
        if owner is not None:
            geomlog("_update_client_geometry: using owner=%s", owner)
            def window_size():
                return  owner.window_size(self)
            def window_position(w, h):
                return  owner.window_position(self, w, h)
            self._do_update_client_geometry(window_size, window_position)
        elif not self._setup_done:
            #try to honour initial size and position requests during setup:
            def window_size():
                return self.get_property("requested-size")
            def window_position(w=0, h=0):
                return self.get_property("requested-position")
            geomlog("_update_client_geometry: using initial size=%s and position=%s", window_size(), window_position())
            self._do_update_client_geometry(window_size, window_position)

    def _do_update_client_geometry(self, window_size_cb, window_position_cb):
        allocated_w, allocated_h = window_size_cb()
        geomlog("_do_update_client_geometry: %sx%s", allocated_w, allocated_h)
        hints = self.get_property("size-hints")
        geomlog("_do_update_client_geometry: hints=%s", hints)
        size = calc_constrained_size(allocated_w, allocated_h, hints)
        geomlog("_do_update_client_geometry: size=%s", size)
        w, h, wvis, hvis = size
        x, y = window_position_cb(w, h)
        geomlog("_do_update_client_geometry: position=%s", (x,y))
        self.corral_window.move_resize(x, y, w, h)
        self._internal_set_property("actual-size", (w, h))
        self._internal_set_property("user-friendly-size", (wvis, hvis))
        with xswallow:
            X11Window.configureAndNotify(self.xid, 0, 0, w, h)

    def do_xpra_configure_event(self, event):
        geomlog("WindowModel.do_xpra_configure_event(%s) corral=%#x, client=%#x, managed=%s", event, self.corral_window.xid, self.xid, self._managed)
        if not self._managed:
            return
        if event.window!=self.client_window:
            #we only care about events on the client window
            geomlog("WindowModel.do_xpra_configure_event: event is not on the client window")
            return
        if self.corral_window is None or not self.corral_window.is_visible():
            geomlog("WindowModel.do_xpra_configure_event: corral window is not visible")
            return
        if self.client_window is None or not self.client_window.is_visible():
            geomlog("WindowModel.do_xpra_configure_event: client window is not visible")
            return
        try:
            #workaround applications whose windows disappear from underneath us:
            with xsync:
                if self.resize_corral_window(event.x, event.y, event.width, event.height, event.border_width):
                    self.notify("geometry")
        except XError as e:
            geomlog.warn("failed to resize corral window: %s", e)

    def resize_corral_window(self, x, y, w, h, border):
        #the client window may have been resized or moved (generally programmatically)
        #so we may need to update the corral_window to match
        cox, coy, cow, coh = self.corral_window.get_geometry()[:4]
        modded = False
        if self._geometry[4]!=border:
            modded = True
        #size changes (and position if any):
        hints = self.get_property("size-hints")
        size = calc_constrained_size(w, h, hints)
        geomlog("resize_corral_window() new constrained size=%s", size)
        w, h, wvis, hvis = size
        if cow!=w or coh!=h:
            if (x, y) != (0, 0):
                geomlog("resize_corral_window() move and resize from %s to %s", (cox, coy, cow, coh), (x, y, w, h))
                self.corral_window.move_resize(x, y, w, h)
                self.client_window.move(0, 0)
                cox, coy, cow, coh = x, y, w, h
            else:
                #just resize:
                geomlog("resize_corral_window() resize from %s to %s", (cow, coh), (w, h))
                self.corral_window.resize(w, h)
                cow, coh = w, h
            modded = True
        #just position change:
        elif (x, y) != (0, 0):
            geomlog("resize_corral_window() moving corral window from %s to %s", (cox, coy), (x, y))
            self.corral_window.move(x, y)
            self.client_window.move(0, 0)
            cox, coy = x, y
            modded = True

        #these two should be using geometry rather than duplicating it?
        if self.get_property("actual-size")!=(w, h):
            self._internal_set_property("actual-size", (w, h))
            modded = True
        if self.get_property("user-friendly-size")!=(wvis, hvis):
            self._internal_set_property("user-friendly-size", (wvis, hvis))
            modded = True

        if modded:
            self._geometry = (cox, coy, cow, coh, border)
        geomlog("resize_corral_window() modified=%s, geometry=%s", modded, self._geometry)
        return modded

    def do_child_configure_request_event(self, event):
        geomlog("do_child_configure_request_event(%s) client=%#x, corral=%#x, value_mask=%s", event, self.xid, self.corral_window.xid, configure_bits(event.value_mask))
        if event.value_mask & CWStackMode:
            geomlog(" restack above=%s, detail=%s", event.above, event.detail)
        # Also potentially update our record of what the app has requested:
        (x, y) = self.get_property("requested-position")
        if event.value_mask & CWX:
            x = event.x
        if event.value_mask & CWY:
            y = event.y
        self._internal_set_property("requested-position", (x, y))

        (w, h) = self.get_property("requested-size")
        if event.value_mask & CWWidth:
            w = event.width
        if event.value_mask & CWHeight:
            h = event.height
        self._internal_set_property("requested-size", (w, h))
        # As per ICCCM 4.1.5, even if we ignore the request
        # send back a synthetic ConfigureNotify telling the client that nothing has happened.
        geomlog("do_child_configure_request_event updated requested geometry: %s", (x, y, w, h))
        self._update_client_geometry()

        # FIXME: consider handling attempts to change stacking order here.
        # (In particular, I believe that a request to jump to the top is
        # meaningful and should perhaps even be respected.)


    #########################################
    # X11 properties synced to Python objects
    #########################################

    def _handle_icon_title_change(self):
        icon_name = self.prop_get("_NET_WM_ICON_NAME", "utf8", True)
        iconlog("_NET_WM_ICON_NAME=%s", icon_name)
        if icon_name is None:
            icon_name = self.prop_get("WM_ICON_NAME", "latin1", True)
            iconlog("WM_ICON_NAME=%s", icon_name)
        self._updateprop("icon-title", sanestr(icon_name))

    def _handle_motif_wm_hints_change(self):
        #motif_hints = self.prop_get("_MOTIF_WM_HINTS", "motif-hints")
        motif_hints = prop_get(self.client_window, "_MOTIF_WM_HINTS", "motif-hints", ignore_errors=False, raise_xerrors=True)
        metalog("_MOTIF_WM_HINTS=%s", motif_hints)
        if motif_hints and motif_hints.flags&(2**MotifWMHints.DECORATIONS_BIT):
            self._updateprop("decorations", motif_hints.decorations)

    def _handle_net_wm_icon_change(self):
        iconlog("_NET_WM_ICON changed on %#x, re-reading", self.xid)
        surf = self.prop_get("_NET_WM_ICON", "icon")
        if surf is not None:
            # FIXME: There is no Pixmap.new_for_display(), so this isn't
            # actually display-clean.  Oh well.
            pixmap = gtk.gdk.Pixmap(None, surf.get_width(), surf.get_height(), 32)
            screen = get_display_for(pixmap).get_default_screen()
            pixmap.set_colormap(screen.get_rgba_colormap())
            cr = pixmap.cairo_create()
            cr.set_source_surface(surf)
            # Important to use SOURCE, because a newly created Pixmap can have
            # random trash as its contents, and otherwise that will show
            # through any alpha in the icon:
            cr.set_operator(cairo.OPERATOR_SOURCE)
            cr.paint()
        else:
            pixmap = None
        #FIXME: it would be more efficient to notify first,
        #then get the icon pixels on demand and cache them..
        self._internal_set_property("icon", surf)
        self._internal_set_property("icon-pixmap", pixmap)
        iconlog("icon is now %r", surf)

    _x11_property_handlers = dict(BaseWindowModel._x11_property_handlers)
    _x11_property_handlers.update({
        "WM_ICON_NAME"                  : _handle_icon_title_change,
        "_NET_WM_ICON_NAME"             : _handle_icon_title_change,
        "_MOTIF_WM_HINTS"               : _handle_motif_wm_hints_change,
        "_NET_WM_ICON"                  : _handle_net_wm_icon_change,
       })


    def get_default_window_icon(self):
        #return the icon which would be used from the wmclass
        c_i = self.get_property("class-instance")
        if not c_i or len(c_i)!=2:
            return None
        wmclass_name, wmclass_class = [x.encode("utf-8") for x in c_i]
        iconlog("get_default_window_icon() using %s", (wmclass_name, wmclass_class))
        if not wmclass_name:
            return None
        it = gtk.icon_theme_get_default()
        i = it.lookup_icon(wmclass_name, 48, 0)
        iconlog("%s.lookup_icon(%s)=%s", it, wmclass_name, i)
        if not i:
            return None
        p = i.load_icon()
        iconlog("%s.load_icon()=%s", i, p)
        if not p:
            return None
        #to make it consistent with the "icon" property,
        #return a cairo surface..
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, p.get_width(), p.get_height())
        gc = gtk.gdk.CairoContext(cairo.Context(surf))
        gc.set_source_pixbuf(p, 0, 0)
        gc.paint()
        iconlog("get_default_window_icon()=%s", surf)
        return surf

    def get_wm_state(self, prop):
        state_names = self._state_properties.get(prop)
        assert state_names, "invalid window state %s" % prop
        log("get_wm_state(%s) state_names=%s", prop, state_names)
        #this is a virtual property for _NET_WM_STATE:
        #return True if any is set (only relevant for maximized)
        for x in state_names:
            if self._state_isset(x):
                return True
        return False


    ################################
    # Focus handling:
    ################################

    def give_client_focus(self):
        """The focus manager has decided that our client should receive X
        focus.  See world_window.py for details."""
        if self.corral_window:
            with xswallow:
                self.do_give_client_focus()

    def do_give_client_focus(self):
        focuslog("Giving focus to %#x", )
        # Have to fetch the time, not just use CurrentTime, both because ICCCM
        # says that WM_TAKE_FOCUS must use a real time and because there are
        # genuine race conditions here (e.g. suppose the client does not
        # actually get around to requesting the focus until after we have
        # already changed our mind and decided to give it to someone else).
        now = gtk.gdk.x11_get_server_time(self.corral_window)
        # ICCCM 4.1.7 *claims* to describe how we are supposed to give focus
        # to a window, but it is completely opaque.  From reading the
        # metacity, kwin, gtk+, and qt code, it appears that the actual rules
        # for giving focus are:
        #   -- the WM_HINTS input field determines whether the WM should call
        #      XSetInputFocus
        #   -- independently, the WM_TAKE_FOCUS protocol determines whether
        #      the WM should send a WM_TAKE_FOCUS ClientMessage.
        # If both are set, both methods MUST be used together. For example,
        # GTK+ apps respect WM_TAKE_FOCUS alone but I'm not sure they handle
        # XSetInputFocus well, while Qt apps ignore (!!!) WM_TAKE_FOCUS
        # (unless they have a modal window), and just expect to get focus from
        # the WM's XSetInputFocus.
        if bool(self._input_field):
            focuslog("... using XSetInputFocus")
            X11Window.XSetInputFocus(self.xid, now)
        if "WM_TAKE_FOCUS" in self.get_property("protocols"):
            focuslog("... using WM_TAKE_FOCUS")
            send_wm_take_focus(self.client_window, now)
        self.set_active()


gobject.type_register(WindowModel)
