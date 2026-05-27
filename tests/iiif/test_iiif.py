from fractions import Fraction

import pytest

from papaya.iiif.image import ImageParams, ImageInfo


def test_image_params_to_string():
    params = ImageParams(
        region='full',
        size='100,100',
        rotation='90',
        quality='default',
        format='png',
    )
    assert str(params) == '/full/100,100/90/default.png'


@pytest.mark.parametrize(
    ('image_format', 'expected_mime_type'),
    [
        ('png', 'image/png'),
        ('jpg', 'image/jpeg'),
        ('tif', 'image/tiff'),
        ('webp', 'image/webp'),
        ('jp2', 'image/jp2'),
        ('pdf', 'application/pdf'),
        ('gif', 'image/gif'),
        ('foo', 'application/octet-stream'),
    ]
)
def test_image_params_to_string(image_format, expected_mime_type):
    params = ImageParams(
        region='full',
        size='100,100',
        rotation='90',
        quality='default',
        format=image_format,
    )
    assert params.mime_type == expected_mime_type


def test_image_info_aspect_ratio():
    info = ImageInfo(
        uri='http://example.com/foo',
        context='',
        profile='',
        width=1024,
        height=768,
    )
    assert info.aspect_ratio == Fraction(4, 3)
