from fractions import Fraction
from unittest.mock import patch, MagicMock

import pytest

from papaya.iiif2 import ImageParams, ImageInfo, ImageService


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


@patch('papaya.iiif2.requests')
def test_image_service_get_metadata(mock_requests):
    mock_response = MagicMock(ok=True)
    mock_response.json.return_value = {
        '@id': 'http://example.com/iiif2/foo',
        '@context': 'iiif2',
        'profile': {},
        'width': 1024,
        'height': 768,
    }
    mock_requests.get.return_value = mock_response
    service = ImageService('http://example.com/iiif2')
    info = service.get_metadata('foo')
    assert info.uri == 'http://example.com/iiif2/foo'
    assert info.context == 'iiif2'
    assert info.profile == {}
    assert info.width == 1024
    assert info.height == 768


@patch('papaya.iiif2.requests')
def test_image_service_get_metadata_problem(mock_requests):
    mock_response = MagicMock(ok=False)
    mock_requests.get.return_value = mock_response
    service = ImageService('http://example.com/iiif2')
    with pytest.raises(RuntimeError):
        service.get_metadata('foo')
