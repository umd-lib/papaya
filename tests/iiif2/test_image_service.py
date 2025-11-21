from unittest.mock import patch, MagicMock

import pytest
import requests
from requests import Response

from papaya.iiif2 import ImageService, ImageServiceError


@patch('papaya.iiif2.requests.get')
def test_image_service_get_metadata(mock_get):
    mock_response = MagicMock(ok=True)
    mock_response.json.return_value = {
        '@id': 'http://example.com/iiif2/foo',
        '@context': 'iiif2',
        'profile': {},
        'width': 1024,
        'height': 768,
    }
    mock_get.return_value = mock_response
    service = ImageService('http://example.com/iiif2')
    info = service.get_metadata('foo')
    assert info.uri == 'http://example.com/iiif2/foo'
    assert info.context == 'iiif2'
    assert info.profile == {}
    assert info.width == 1024
    assert info.height == 768


@patch('papaya.iiif2.requests.get')
def test_image_service_get_metadata_connection_error(mock_get):
    mock_get.side_effect = requests.ConnectionError()
    service = ImageService('http://example.com/iiif2')
    with pytest.raises(ImageServiceError):
        service.get_metadata('foo')


@patch('papaya.iiif2.requests.get')
def test_image_service_get_metadata_problem(mock_get):
    mock_get.return_value = MagicMock(spec=Response, ok=False, status_code=400)
    service = ImageService('http://example.com/iiif2')
    with pytest.raises(ImageServiceError):
        service.get_metadata('foo')
