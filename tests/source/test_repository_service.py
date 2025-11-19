import pytest

from papaya.source import RepositoryService, IdentifierError, URLError


@pytest.fixture
def repo_service():
    return RepositoryService(endpoint='http://example.com/fcrepo/rest', prefix='fcrepo:')


def test_get_resource_uri(repo_service):
    assert repo_service.get_resource_uri('fcrepo:foo:bar:baz') == 'http://example.com/fcrepo/rest/foo/bar/baz'


def test_get_resource_uri_no_prefix(repo_service):
    with pytest.raises(IdentifierError):
        repo_service.get_resource_uri('no_prefix_in_this_identifier')


def test_get_resource_uri_wrong_prefix(repo_service):
    with pytest.raises(IdentifierError):
        repo_service.get_resource_uri('wrong_prefix:in_this_identifier')


def test_get_iiif_id(repo_service):
    assert repo_service.get_iiif_id('http://example.com/fcrepo/rest/thing/1/2') == 'fcrepo:thing:1:2'


def test_get_iiif_id_wrong_endpoint(repo_service):
    with pytest.raises(URLError):
        repo_service.get_iiif_id('http://different.example.net/fcrepo/rest/foo/bar')
