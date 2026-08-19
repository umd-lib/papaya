from fractions import Fraction
from unittest.mock import MagicMock

import pytest
import requests

from papaya.iiif import DEFAULT_UNAVAILABLE_IMAGE_ID, IMAGE_API_2_CONTEXT, IMAGE_API_2_PROFILE_LEVEL_2
from papaya.iiif.image import ImageParams, ImageInfo, ImageService
from papaya.iiif.presentation import Image


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


def test_image_unavailable(monkeypatch, caplog):
    monkeypatch.setattr(requests, 'get', lambda _url, headers: MagicMock(spec=requests.Response, ok=False, status_code=500))  # noqa
    service = ImageService(endpoint='http://example.com/iiif', unavailable_image_id=DEFAULT_UNAVAILABLE_IMAGE_ID)
    image = Image(service, image_id='foo')
    info = image.info
    assert info.uri == 'http://example.com/iiif/static:unavailable'
    assert info.context == IMAGE_API_2_CONTEXT
    assert info.profile == IMAGE_API_2_PROFILE_LEVEL_2
    assert info.width == 200
    assert info.height == 200
    assert 'Unable to retrieve image info' in caplog.text
    assert 'Using the placeholder "unavailable" image' in caplog.text
