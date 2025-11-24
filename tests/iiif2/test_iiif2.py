from fractions import Fraction

from papaya.iiif2 import ImageParams, ImageInfo


def test_image_params_to_string():
    params = ImageParams(
        region='full',
        size='100,100',
        rotation='90',
        quality='default',
        format='png',
    )
    assert str(params) == '/full/100,100/90/default.png'


def test_image_info_aspect_ratio():
    info = ImageInfo(
        uri='http://example.com/foo',
        context='',
        profile='',
        width=1024,
        height=768,
    )
    assert info.aspect_ratio == Fraction(4, 3)
