# This file is part of Xpra.
# Copyright (C) 2016 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import time
import os

from xpra.log import Logger
from _dbus_bindings import UInt32
log = Logger("webcam")

from xpra.codecs.image_wrapper import ImageWrapper


from libc.stdint cimport uint32_t, uint8_t

cdef extern from "../../buffers/memalign.h":
    void *xmemalign(size_t size) nogil
    void *memset(void * ptr, int value, size_t num)

cdef extern from "stdlib.h":
    void free(void* ptr)

cdef extern from "string.h":
    void * memcpy ( void * destination, void * source, size_t num )


cdef extern from "../../buffers/buffers.h":
    int object_as_buffer(object obj, const void ** buffer, Py_ssize_t * buffer_len)
    int get_buffer_api_version()


cdef extern from *:
    ctypedef unsigned long size_t

cdef extern from "sys/ioctl.h":
    int ioctl(int fd, unsigned long request, ...)

cdef extern from "linux/videodev2.h":
    int VIDIOC_QUERYCAP
    int VIDIOC_G_FMT
    int VIDIOC_S_FMT
    int V4L2_COLORSPACE_SRGB
    int V4L2_FIELD_NONE
    int V4L2_BUF_TYPE_VIDEO_OUTPUT
    #formats:
    int V4L2_PIX_FMT_GREY
    int V4L2_PIX_FMT_YUV422P
    int V4L2_PIX_FMT_YUV420
    int V4L2_PIX_FMT_YVU420

    cdef struct v4l2_capability:
        uint8_t driver[16]
        uint8_t card[32]
        uint8_t bus_info[32]
        uint32_t version
        uint32_t capabilities
        uint32_t device_caps
        uint32_t reserved[3]

    cdef struct v4l2_pix_format:
        uint32_t width
        uint32_t height
        uint32_t pixelformat
        uint32_t field          # enum v4l2_field */
        uint32_t bytesperline   # for padding, zero if unused */
        uint32_t sizeimage
        uint32_t colorspace     # enum v4l2_colorspace */
        uint32_t priv           # private data, depends on pixelformat */
        uint32_t flags          # format flags (V4L2_PIX_FMT_FLAG_*) */
        uint32_t ycbcr_enc      # enum v4l2_ycbcr_encoding */
        uint32_t quantization   # enum v4l2_quantization */
        uint32_t xfer_func      # enum v4l2_xfer_func */

        pass
    cdef struct v4l2_pix_format_mplane:
        pass
    cdef struct v4l2_window:
        pass
    cdef struct v4l2_vbi_format:
        pass
    cdef struct v4l2_sliced_vbi_format:
        pass
    cdef struct v4l2_sdr_format:
        pass

    cdef union v4l2_format_fmt:
        v4l2_pix_format          pix        #V4L2_BUF_TYPE_VIDEO_CAPTURE
        v4l2_pix_format_mplane   pix_mp     #V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE
        v4l2_window              win        #V4L2_BUF_TYPE_VIDEO_OVERLAY
        v4l2_vbi_format          vbi        #V4L2_BUF_TYPE_VBI_CAPTURE
        v4l2_sliced_vbi_format   sliced     #V4L2_BUF_TYPE_SLICED_VBI_CAPTURE
        v4l2_sdr_format          sdr        #V4L2_BUF_TYPE_SDR_CAPTURE
        uint8_t raw_data[200]               #user-defined

    cdef struct v4l2_format:
        uint32_t type
        v4l2_format_fmt fmt

cdef inline int roundup(int n, int m):
    return (n + m - 1) & ~(m - 1)


def init_module():
    log("v4l2.pusher.init_module()")

def cleanup_module():
    log("v4l2pusher.cleanup_module()")

def get_version():
    return 0

def get_type():
    return "v4l2"

def get_info():
    global COLORSPACES, MAX_WIDTH, MAX_HEIGHT
    return {"version"   : get_version(),
            "buffer_api": get_buffer_api_version()}

def get_input_colorspaces():
    return  ["YUV420P"]


cdef class Pusher:
    cdef unsigned long frames
    cdef int width
    cdef int height
    cdef int rowstride
    cdef size_t framesize
    cdef object src_format
    cdef object device
    cdef object device_name

    cdef object __weakref__

    def init_context(self, int width, int height, int rowstride, src_format, device):    #@DuplicatedSignature
        assert src_format in get_input_colorspaces(), "invalid source format '%s', must be one of %s" % (src_format, get_input_colorspaces())
        self.width = width
        self.height = height
        self.rowstride = rowstride
        self.src_format = src_format
        self.frames = 0
        self.init_device(device)
    
    cdef init_device(self, device):
        cdef v4l2_capability vid_caps
        cdef v4l2_format vid_format
        self.device_name = device or os.environ.get("XPRA_VIDEO_DEVICE", "/dev/video1")
        log("v4l2 using device %s", self.device_name)
        self.device = open(self.device_name, "wb")
        r = ioctl(self.device.fileno(), VIDIOC_QUERYCAP, &vid_caps)
        log("ioctl(%s, VIDIOC_QUERYCAP, %#x)=%s", self.device_name, <unsigned long> &vid_caps, r)
        assert r!=-1, "VIDIOC_QUERYCAP ioctl failed on %s" % self.device_name
        memset(&vid_format, 0, sizeof(vid_format))
        r = ioctl(self.device.fileno(), VIDIOC_G_FMT, &vid_format)
        log("ioctl(%s, VIDIOC_G_FMT, %#x)=%s", self.device_name, <unsigned long> &vid_format, r)
        self.show_vid_format(&vid_format)
        #assert r!=-1, "VIDIOC_G_FMT ioctl failed on %s" % self.device_name
        vid_format.type = V4L2_BUF_TYPE_VIDEO_OUTPUT
        vid_format.fmt.pix.width = self.width
        vid_format.fmt.pix.height = self.height
        #self.framesize = self.height*self.rowstride*3//2
        #vid_format.fmt.pix.pixelformat = V4L2_PIX_FMT_YUV420        #V4L2_PIX_FMT_YVU420
        self.framesize = self.height*self.rowstride
        vid_format.fmt.pix.pixelformat = V4L2_PIX_FMT_GREY
        vid_format.fmt.pix.sizeimage = self.framesize
        vid_format.fmt.pix.field = V4L2_FIELD_NONE
        vid_format.fmt.pix.bytesperline = 0
        vid_format.fmt.pix.colorspace = V4L2_COLORSPACE_SRGB
        r = ioctl(self.device.fileno(), VIDIOC_S_FMT, &vid_format)
        log("ioctl(%s, VIDIOC_S_FMT, %#x)=%s", self.device_name, <unsigned long> &vid_format, r)
        assert r!=-1, "VIDIOC_S_FMT ioctl failed on %s" % self.device_name
        self.show_vid_format(&vid_format)
        self.width = vid_format.fmt.pix.width
        self.height = vid_format.fmt.pix.height
        self.rowstride = vid_format.fmt.pix.bytesperline
        self.framesize = self.height*self.rowstride
        parsed_pixel_format = self.parse_pixel_format(&vid_format)
        self.src_format = self.get_equiv_format(parsed_pixel_format)
        assert self.src_format in get_input_colorspaces(), "invalid pixel format used: %s" % self.src_format


    def get_equiv_format(self, fmt):
        return {"YU12" : "YUV420P", "YV12" : "YVU420P", "GREY" : "YUV420P"}.get(fmt, fmt)

    cdef parse_pixel_format(self, v4l2_format *vid_format):
        if vid_format.fmt.pix.pixelformat==0:
            return ""
        return "".join([chr((vid_format.fmt.pix.pixelformat//(2**(8*x))) % 256) for x in range(4)])

    cdef show_vid_format(self, v4l2_format *vid_format):
        log("vid_format.type                 = %i", vid_format.type)
        log("vid_format.fmt.pix.width        = %i", vid_format.fmt.pix.width)
        log("vid_format.fmt.pix.height       = %i", vid_format.fmt.pix.height)
        parsed_pixel_format = self.parse_pixel_format(vid_format)
        equiv = self.get_equiv_format(parsed_pixel_format)
        log("vid_format.fmt.pix.pixelformat  = %s = %s (for %#x)", parsed_pixel_format or "unset", equiv or "unset", vid_format.fmt.pix.pixelformat)
        log("vid_format.fmt.pix.sizeimage    = %i", vid_format.fmt.pix.sizeimage)
        log("vid_format.fmt.pix.field        = %i", vid_format.fmt.pix.field)
        log("vid_format.fmt.pix.bytesperline = %i", vid_format.fmt.pix.bytesperline)
        log("vid_format.fmt.pix.colorspace   = %i", vid_format.fmt.pix.colorspace)


    def clean(self):                        #@DuplicatedSignature
        self.width = 0
        self.height = 0
        self.rowstride = 0
        self.src_format = ""
        self.frames = 0
        self.framesize = 0

    def get_info(self):             #@DuplicatedSignature
        info = get_info()
        info.update({"frames"    : self.frames,
                     "width"     : self.width,
                     "height"    : self.height,
                     "src_format": self.src_format})
        return info

    def __repr__(self):
        if self.src_format is None:
            return "v4l2.Pusher(uninitialized)"
        return "v4l2.Pusher(%s - %sx%s)" % (self.src_format, self.width, self.height)

    def is_closed(self):
        return not bool(self.src_format)

    def __dealloc__(self):
        self.clean()

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height

    def get_type(self):                     #@DuplicatedSignature
        return  "v4l2"

    def get_src_format(self):
        return self.src_format


    def push_image(self, image):
        cdef unsigned char *Ybuf
        cdef unsigned char *Ubuf
        cdef unsigned char *Vbuf
        cdef unsigned int Ystride, Ustride, Vstride
        cdef Py_ssize_t buf_len = 0
        cdef unsigned int chroma_h
        cdef unsigned int chroma_div
        cdef uint8_t* buf

        chroma_div = 2
        chroma_h = self.height//chroma_div

        iplanes = image.get_planes()
        assert iplanes==ImageWrapper._3_PLANES, "invalid input format: %s planes" % iplanes
        assert image.get_width()>=self.width, "invalid image width: %s (minimum is %s)" % (image.get_width(), self.width)
        assert image.get_height()>=self.height, "invalid image height: %s (minimum is %s)" % (image.get_height(), self.height)
        planes = image.get_pixels()
        assert planes, "failed to get pixels from %s" % image
        input_strides = image.get_rowstride()
        log("push_image(%s) strides=%s, video stride=%s, chroma_h=%s", (image), input_strides, self.rowstride, chroma_h)
        Ystride, Ustride, Vstride = input_strides
        assert Ystride==self.rowstride, "invalid stride: %s but expected %s" % (Ystride, self.rowstride)
        assert Ustride==self.rowstride//chroma_div
        assert Vstride==self.rowstride//chroma_div
        assert object_as_buffer(planes[0], <const void**> &Ybuf, &buf_len)==0, "failed to convert %s to a buffer" % type(planes[0])
        assert buf_len>=Ystride*image.get_height(), "buffer for Y plane is too small: %s bytes, expected at least %s" % (buf_len, Ystride*image.get_height())
        assert object_as_buffer(planes[1], <const void**> &Ubuf, &buf_len)==0, "failed to convert %s to a buffer" % type(planes[1])
        assert buf_len>=Ustride*image.get_height()//chroma_div, "buffer for U plane is too small: %s bytes, expected at least %s" % (buf_len, Ustride*image.get_height()//chroma_div)
        assert object_as_buffer(planes[2], <const void**> &Vbuf, &buf_len)==0, "failed to convert %s to a buffer" % type(planes[2])
        assert buf_len>=Vstride*image.get_height()//chroma_div, "buffer for V plane is too small: %s bytes, expected at least %s" % (buf_len, Vstride*image.get_height()//chroma_div)
        #assert Ystride*self.height+Ustride*chroma_h+Vstride*chroma_h <= self.framesize, "buffer %i is too small for %i + %i + %i" % (self.framesize, Ystride*self.height, Ustride*chroma_h, Vstride*chroma_h)

        cdef int offset = roundup(self.rowstride//2, 32)
        buf = <uint8_t*> xmemalign(self.framesize + offset + self.rowstride)
        assert buf!=NULL, "failed to allocate temporary output buffer"
        cdef int i
        for i in range(self.height//4):
            memcpy(buf+offset+(0+i*4)*self.rowstride, Ybuf+(i*4)*Ystride, self.width)
            memcpy(buf+offset+(1+i*4)*self.rowstride, Ybuf+(i*4)*Ystride, self.width)
            memcpy(buf+offset+(2+i*4)*self.rowstride, Ybuf+(i*4)*Ystride, self.width)
            memcpy(buf+offset+(3+i*4)*self.rowstride, Ybuf+(i*4)*Ystride, self.width)
        self.device.write(buf[:self.framesize])
        self.device.flush()
        free(buf)


def selftest(full=False):
    pass