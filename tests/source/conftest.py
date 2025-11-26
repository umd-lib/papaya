import pytest


@pytest.fixture
def solr_doc():
    return {
        'id': 'http://example.com/fcrepo/123',
        'title__txt': 'Foobar',
        'date__str': '2025-11-25',
        'pages__uris': [
            'http://example.com/fcrepo/123/p/1',
            'http://example.com/fcrepo/123/p/2',
            'http://example.com/fcrepo/123/p/3',
        ],
        'images__ids': [
            'fcrepo:123:p1',
            'fcrepo:123:p2',
            'fcrepo:123:p3',
        ],
        'pages': [
            {
                'id': 'http://example.com/fcrepo/123/p/1',
                'title': 'Page 1',
                'files': [
                    {'id': 'http://example.com/fcrepo/123/f/1'},
                    {'id': 'http://example.com/fcrepo/123/f/2'},
                ],
            },
            {'id': 'http://example.com/fcrepo/123/p/2', 'title': 'Page 2'},
            {'id': 'http://example.com/fcrepo/123/p/3', 'title': 'Page 3'},
        ],
        'license': 'https://rightsstatements.org/vocab/NoC-NC/1.0/',
        'creator': [
            {'name': 'John Doe'},
            {'name': '[@de]Johannes Tier'},
        ],
    }


@pytest.fixture
def metadata_queries():
    return {
        '$uri': '.id',
        '$label': '.title__txt',
        '$page_uris': '.pages__uris[]',
        '$date': '.date__str',
        '$license_uri': '.license',
        '$page_image_ids': '.images__ids[]',
        '$*page_doc': '.pages[]|select(.id == $uri)',
        '$*page_label': '.pages[]|select(.id == $uri).title',
        '$*file_page_uri': '.pages[]|select(.files[].id == $uri).id',
        'Title': '.title__txt',
        'Creator': '.creator[]?.name',
    }
