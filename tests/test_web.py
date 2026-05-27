from http import HTTPStatus

import pytest

from papaya import __version__
from papaya.web import create_app


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv('PAPAYA_SOLR_ENDPOINT', 'http://localhost:8985/solr/fcrepo')
    monkeypatch.setenv('PAPAYA_SOLR_TEXT_MATCH_FIELD', 'extracted_text__dps_txt')
    monkeypatch.setenv('PAPAYA_FCREPO_ENDPOINT', 'http://fcrepo-local:8080/fcrepo/rest')
    monkeypatch.setenv('PAPAYA_FCREPO_PREFIX', 'fcrepo:')
    monkeypatch.setenv('PAPAYA_IIIF_IMAGE_ENDPOINT', 'http://localhost:8182/iiif/2')
    monkeypatch.setenv('PAPAYA_URL', 'http://localhost/manifests')
    return create_app()


@pytest.fixture
def client(app):
    return app.test_client()


def test_root(client):
    response = client.get('/')
    assert response.status_code == HTTPStatus.FOUND
    assert response.headers['Location'] == '/manifests/'


def test_manifests_form(client):
    response = client.get('/manifests/')
    assert response.status_code == HTTPStatus.OK
    assert 'Papaya' in response.text
    assert __version__ in response.text


def test_find_manifest(client):
    response = client.post('/manifests/', data={'uri': 'http://fcrepo-local:8080/fcrepo/rest/123'})
    assert response.status_code == HTTPStatus.FOUND
    assert response.headers['Location'] == '/manifests/fcrepo:123/manifest'


@pytest.mark.parametrize(
    ('request_path', 'canonical_url'),
    [
        ('/manifests/foobar/manifest.json', '/manifests/foobar/manifest'),
        ('/manifests/foobar/', '/manifests/foobar/manifest'),
        # preserves query string
        ('/manifests/foobar/manifest.json?q=swordfish', '/manifests/foobar/manifest?q=swordfish'),
        ('/manifests/foobar/?q=swordfish', '/manifests/foobar/manifest?q=swordfish'),
        ('/manifests/foobar/manifest.json?ANY_STRING', '/manifests/foobar/manifest?ANY_STRING'),
        ('/manifests/foobar/?ANY_STRING', '/manifests/foobar/manifest?ANY_STRING'),
    ]
)
def test_redirect_to_manifest(client, request_path, canonical_url):
    response = client.get(request_path)
    assert response.status_code == HTTPStatus.MOVED_PERMANENTLY
    assert response.headers['Location'] == canonical_url
