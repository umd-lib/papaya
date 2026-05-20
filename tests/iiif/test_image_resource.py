import pytest
from urlobject import URLObject

from papaya.iiif.image import ImageParams, ImageResource


@pytest.mark.parametrize(
    ('endpoint', 'origin', 'image_id', 'expected_image_uri', 'expected_request_url'),
    [
        (
            URLObject('https://iiif.example.com/images/iiif/2'),
            None,
            'foo:123',
            'https://iiif.example.com/images/iiif/2/foo:123',
            'https://iiif.example.com/images/iiif/2/foo:123',
        ),
        (
            URLObject('https://iiif.example.com/images/iiif/2'),
            URLObject('http://papaya:3001/iiif/2'),
            'foo:123',
            'https://iiif.example.com/images/iiif/2/foo:123',
            'http://papaya:3001/iiif/2/foo:123',
        ),
    ]
)
def test_image_resource_uris(endpoint, origin, image_id, expected_image_uri, expected_request_url):
    resource = ImageResource(endpoint=endpoint, origin=origin, image_id=image_id)
    assert resource.uri() == expected_image_uri
    assert resource.request_url() == expected_request_url


@pytest.mark.parametrize(
    ('endpoint', 'origin', 'expected_headers'),
    [
        # no separate origin URL
        (
            URLObject('https://iiif.example.com/images/iiif/2'),
            None,
            {},
        ),
        # separate origin URL, paths identical
        (
            URLObject('https://iiif.example.com/iiif/2'),
            URLObject('http://papaya:3001/iiif/2'),
            {
                'X-Forwarded-Proto': 'https',
                'X-Forwarded-Host': 'iiif.example.com',
            },
        ),
        # separate origin URL, endpoint path has an extra prefix compared to origin path
        (
                URLObject('https://iiif.example.com/images/iiif/2'),
                URLObject('http://papaya:3001/iiif/2'),
                {
                    'X-Forwarded-Proto': 'https',
                    'X-Forwarded-Host': 'iiif.example.com',
                    'X-Forwarded-Path': '/images',
                },
        ),
    ]
)
def test_image_resource_forwarding_headers(endpoint, origin, expected_headers):
    resource = ImageResource(endpoint=endpoint, origin=origin, image_id='foobar')
    assert resource.forwarding_headers == expected_headers


@pytest.mark.parametrize(
    ('params', 'expected_uri', 'expected_request_url'),
    [
        (
            None,
            'https://iiif.example.com/iiif/2/foo:123',
            'http://papaya:3001/iiif/2/foo:123',
        ),
        (
            ImageParams(
                region='full',
                size='100,100',
                rotation='90',
                quality='default',
                format='png',
            ),
            'https://iiif.example.com/iiif/2/foo:123/full/100,100/90/default.png',
            'http://papaya:3001/iiif/2/foo:123/full/100,100/90/default.png',
        ),
    ]
)
def test_image_resource_with_params(params, expected_uri, expected_request_url):
    resource = ImageResource(
        endpoint=URLObject('https://iiif.example.com/iiif/2'),
        origin=URLObject('http://papaya:3001/iiif/2'),
        image_id='foo:123',
    )
    assert resource.uri(params) == expected_uri
    assert resource.request_url(params) == expected_request_url
