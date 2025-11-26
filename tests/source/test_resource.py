import pytest

from papaya.source import Resource


@pytest.fixture
def resource(solr_doc, metadata_queries):
    return Resource(doc=solr_doc, metadata_queries=metadata_queries)


def test_uri(resource):
    assert resource.uri == 'http://example.com/fcrepo/123'


def test_label(resource):
    assert resource.label == 'Foobar'


def test_page_uris(resource):
    assert resource.page_uris == [
        'http://example.com/fcrepo/123/p/1',
        'http://example.com/fcrepo/123/p/2',
        'http://example.com/fcrepo/123/p/3',
    ]


def test_date(resource):
    assert resource.date == '2025-11-25'


def test_license(resource):
    assert resource.license == 'https://rightsstatements.org/vocab/NoC-NC/1.0/'


def test_metadata(resource):
    assert resource.metadata == [
        {'label': 'Title', 'value': ['Foobar']},
        {
            'label': 'Creator',
            'value': [
                'John Doe',
                {'@language': 'de', '@value': 'Johannes Tier'},
            ],
        },
    ]


def test_get_page_doc(resource):
    page_doc = resource.get_page_doc('http://example.com/fcrepo/123/p/2')
    assert page_doc == {'id': 'http://example.com/fcrepo/123/p/2', 'title': 'Page 2'}


def test_find_page_doc(resource):
    assert resource.find_page_doc('http://example.com/fcrepo/123/f/2') == 'http://example.com/fcrepo/123/p/1'


def test_get_page_index(resource):
    assert resource.index('http://example.com/fcrepo/123/p/3') == 2


def test_get_page_image_id(resource):
    assert resource.get_page_image_id('http://example.com/fcrepo/123/p/3') == 'fcrepo:123:p3'


def test_get_page_label(resource):
    assert resource.get_page_label('http://example.com/fcrepo/123/p/2') == 'Page 2'
