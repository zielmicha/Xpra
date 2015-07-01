# coding=utf8
# This file is part of Xpra.
# Copyright (C) 2015 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.


import binascii

from xpra.log import Logger
log = Logger("util")


#this test data was generated using a 24x16 blank image as input
TEST_COMPRESSED_DATA = {
    "h264": {
             "YUV420P" : binascii.unhexlify("000000016764000aacb317cbc2000003000200000300651e244cd00000000168e970312c8b0000010605ffff56dc45e9bde6d948b7962cd820d923eeef78323634202d20636f726520313432202d20482e3236342f4d5045472d342041564320636f646563202d20436f70796c65667420323030332d32303134202d20687474703a2f2f7777772e766964656f6c616e2e6f72672f783236342e68746d6c202d206f7074696f6e733a2063616261633d31207265663d35206465626c6f636b3d313a303a3020616e616c7973653d3078333a3078313133206d653d756d68207375626d653d38207073793d31207073795f72643d312e30303a302e3030206d697865645f7265663d31206d655f72616e67653d3136206368726f6d615f6d653d31207472656c6c69733d31203878386463743d312063716d3d3020646561647a6f6e653d32312c313120666173745f70736b69703d31206368726f6d615f71705f6f66667365743d2d3220746872656164733d31206c6f6f6b61686561645f746872656164733d3120736c696365645f746872656164733d30206e723d3020646563696d6174653d3120696e7465726c616365643d3020626c757261795f636f6d7061743d3020636f6e73747261696e65645f696e7472613d3020626672616d65733d3020776569676874703d32206b6579696e743d393939393939206b6579696e745f6d696e3d353030303030207363656e656375743d343020696e7472615f726566726573683d302072633d637266206d62747265653d30206372663d33382e322071636f6d703d302e36302071706d696e3d302071706d61783d3639207170737465703d342069705f726174696f3d312e34302061713d313a312e3030008000000165888404bffe841fc0a667f891ea1728763fecb5e1"),
             "YUV422P" : binascii.unhexlify("00000001677a000abcb317cbc2000003000200000300651e244cd00000000168e970312c8b0000010605ffff56dc45e9bde6d948b7962cd820d923eeef78323634202d20636f726520313432202d20482e3236342f4d5045472d342041564320636f646563202d20436f70796c65667420323030332d32303134202d20687474703a2f2f7777772e766964656f6c616e2e6f72672f783236342e68746d6c202d206f7074696f6e733a2063616261633d31207265663d35206465626c6f636b3d313a303a3020616e616c7973653d3078333a3078313133206d653d756d68207375626d653d38207073793d31207073795f72643d312e30303a302e3030206d697865645f7265663d31206d655f72616e67653d3136206368726f6d615f6d653d31207472656c6c69733d31203878386463743d312063716d3d3020646561647a6f6e653d32312c313120666173745f70736b69703d31206368726f6d615f71705f6f66667365743d2d3220746872656164733d31206c6f6f6b61686561645f746872656164733d3120736c696365645f746872656164733d30206e723d3020646563696d6174653d3120696e7465726c616365643d3020626c757261795f636f6d7061743d3020636f6e73747261696e65645f696e7472613d3020626672616d65733d3020776569676874703d32206b6579696e743d393939393939206b6579696e745f6d696e3d353030303030207363656e656375743d343020696e7472615f726566726573683d302072633d637266206d62747265653d30206372663d33382e322071636f6d703d302e36302071706d696e3d302071706d61783d3639207170737465703d342069705f726174696f3d312e34302061713d313a312e3030008000000165888404bffe841fc0a667f891ec3d121e72aecb5f"),
             "YUV444P" : binascii.unhexlify("0000000167f4000a919662f89e1000000300100000030328f12266800000000168e970311121100000010605ffff55dc45e9bde6d948b7962cd820d923eeef78323634202d20636f726520313432202d20482e3236342f4d5045472d342041564320636f646563202d20436f70796c65667420323030332d32303134202d20687474703a2f2f7777772e766964656f6c616e2e6f72672f783236342e68746d6c202d206f7074696f6e733a2063616261633d31207265663d35206465626c6f636b3d313a303a3020616e616c7973653d3078333a3078313133206d653d756d68207375626d653d38207073793d31207073795f72643d312e30303a302e3030206d697865645f7265663d31206d655f72616e67653d3136206368726f6d615f6d653d31207472656c6c69733d31203878386463743d312063716d3d3020646561647a6f6e653d32312c313120666173745f70736b69703d31206368726f6d615f71705f6f66667365743d3420746872656164733d31206c6f6f6b61686561645f746872656164733d3120736c696365645f746872656164733d30206e723d3020646563696d6174653d3120696e7465726c616365643d3020626c757261795f636f6d7061743d3020636f6e73747261696e65645f696e7472613d3020626672616d65733d3020776569676874703d32206b6579696e743d393939393939206b6579696e745f6d696e3d353030303030207363656e656375743d343020696e7472615f726566726573683d302072633d637266206d62747265653d30206372663d33382e322071636f6d703d302e36302071706d696e3d302071706d61783d3639207170737465703d342069705f726174696f3d312e34302061713d313a312e3030008000000165888404bffeeb1fc0a667f75e658f9a9fccb1f341ffff"),
             },
    "vp8" : {"YUV420P" : binascii.unhexlify("1003009d012a1800100000070885858899848800281013ad501fc01fd01050122780feffbb029ffffa2546bd18c06f7ffe8951fffe8951af46301bdfffa22a00")},
    "vp9" : {"YUV420P" : binascii.unhexlify("8249834200017000f60038241c18000000200000047ffffffba9da00059fffffff753b413bffffffeea7680000"),
             "YUV444P" : binascii.unhexlify("a249834200002e001ec007048383000000040000223fffffeea76800c7ffffffeea7680677ffffff753b40081000")},
}
W = 24
H = 16


def make_test_image(pixel_format, w, h):
    from xpra.codecs.image_wrapper import ImageWrapper
    from xpra.codecs.codec_constants import get_subsampling_divs
    if pixel_format.startswith("YUV") or pixel_format=="GBRP":
        divs = get_subsampling_divs(pixel_format)
        ydiv = divs[0]  #always (1,1)
        y = bytearray(b"\0" * (w*h//(ydiv[0]*ydiv[1])))
        udiv = divs[1]
        u = bytearray(b"\0" * (w*h//(udiv[0]*udiv[1])))
        vdiv = divs[2]
        v = bytearray(b"\0" * (w*h//(vdiv[0]*vdiv[1])))
        image = ImageWrapper(0, 0, w, h, [y, u, v], pixel_format, 32, [w//ydiv[0], w//udiv[0], w//vdiv[0]], planes=ImageWrapper._3_PLANES, thread_safe=True)
    elif pixel_format in ("RGB", "BGR", "RGBX", "BGRX", "XRGB", "BGRA", "RGBA"):
        rgb_data = bytearray(b"\0" * (w*h*len(pixel_format)))
        image = ImageWrapper(0, 0, w, h, rgb_data, pixel_format, 32, w*len(pixel_format), planes=ImageWrapper.PACKED, thread_safe=True)
    else:
        raise Exception("don't know how to create a %s image" % pixel_format)
    return image


def testdecoder(decoder_module, full):
    codecs = decoder_module.get_encodings()
    for encoding in list(codecs):
        try:
            testdecoding(decoder_module, encoding, full)
        except Exception as e:
            log("%s: %s decoding failed", decoder_module.get_type(), encoding, exc_info=True)
            log.warn("%s: %s decoding failed: %s", decoder_module.get_type(), encoding, e)
            codecs.remove(encoding)
    if not codecs:
        log.error("%s: all the codecs have failed! (%s)", decoder_module.get_type(), ", ".join(decoder_module.get_encodings()))
    return codecs

def testdecoding(decoder_module, encoding, full):
    test_data_set = TEST_COMPRESSED_DATA.get(encoding)
    if not test_data_set:
        log("%s: no test data for %s", decoder_module.get_type(), encoding)
        return
    for cs in decoder_module.get_input_colorspaces(encoding):
        e = decoder_module.Decoder()
        try:
            e.init_context(encoding, W, H, cs)
            test_data = test_data_set.get(cs)
            if test_data:
                log("%s: testing %s / %s with %s bytes of data", decoder_module.get_type(), encoding, cs, len(test_data))
                image = e.decompress_image(test_data, {})
                assert image is not None, "failed to decode test data for encoding '%s' with colorspace '%s'" % (encoding, cs)
                assert image.get_width()==W, "expected image of width %s but got %s" % (W, image.get_width())
                assert image.get_height()==H, "expected image of height %s but got %s" % (H, image.get_height())
            if full:
                log("%s: testing %s / %s with junk data", decoder_module.get_type(), encoding, cs)
                #test failures:
                try:
                    image = e.decompress_image(b"junk", {})
                except:
                    image = None
                if image is not None:
                    raise Exception("decoding junk with %s should have failed, got %s instead" % (decoder_module.get_type(), image))
        finally:
            e.clean()


def testencoder(encoder_module, full):
    codecs = encoder_module.get_encodings()
    for encoding in list(codecs):
        try:
            testencoding(encoder_module, encoding, full)
        except Exception as e:
            log("%s: %s encoding failed", encoder_module.get_type(), encoding, exc_info=True)
            log.warn("%s: %s encoding failed: %s", encoder_module.get_type(), encoding, e)
            codecs.remove(encoding)
    if not codecs:
        log.error("%s: all the codecs have failed! (%s)", encoder_module.get_type(), ", ".join(encoder_module.get_encodings()))
    return codecs

def testencoding(encoder_module, encoding, full):
    for cs_in in encoder_module.get_input_colorspaces(encoding):
        for cs_out in encoder_module.get_output_colorspaces(encoding, cs_in):
            e = encoder_module.Encoder()
            try:
                e.init_context(W, H, cs_in, [cs_out], encoding, W, H, (1,1), {})
                image = make_test_image(cs_in, W, H)
                data, meta = e.compress_image(image)
                assert len(data)>0
                assert meta is not None
                #print("test_encoder: %s.compress_image(%s)=%s" % (encoder_module.get_type(), image, (data, meta)))
                #print("compressed data with %s: %s bytes (%s), metadata: %s" % (encoder_module.get_type(), len(data), type(data), meta))
                #print("compressed data(%s, %s)=%s" % (encoding, cs_in, binascii.hexlify(data)))
                if full:
                    try:
                        wrong_format = [x for x in ("YUV420P", "YUV444P", "BGRX") if x!=cs_in][0]
                        image = make_test_image(wrong_format, W, H)
                        out = e.compress_image()
                    except:
                        out = None
                    assert out is None
                    for w,h in ((W*2, H//2), (W//2, H**2)):
                        try:
                            image = make_test_image(cs_in, w, h)
                            out = e.compress_image()
                        except:
                            out = None
                        assert out is None
            finally:
                e.clean()


def testcsc(csc_module, full):
    for cs_in in csc_module.get_input_colorspaces():
        for cs_out in csc_module.get_output_colorspaces(cs_in):
            log("%s: testing %s / %s", csc_module.get_type(), cs_in, cs_out)
            e = csc_module.ColorspaceConverter()
            try:
                #TODO: test scaling
                e.init_context(W, H, cs_in, W, H, cs_out)
                image = make_test_image(cs_in, W, H)
                out = e.convert_image(image)
                #print("convert_image(%s)=%s" % (image, out))
                assert out.get_width()==W, "expected image of width %s but got %s" % (W, image.get_width())
                assert out.get_height()==H, "expected image of height %s but got %s" % (H, image.get_height())
                assert out.get_pixel_format()==cs_out
                if full:
                    for w,h in ((W*2, H//2), (W//2, H**2)):
                        try:
                            image = make_test_image(cs_in, w, h)
                            out = e.convert_image(image)
                        except:
                            out = None
                        if out is not None:
                            raise Exception("converting an image of a smaller size with %s should have failed, got %s instead" % (csc_module.get_type(), out))
            finally:
                e.clean()
