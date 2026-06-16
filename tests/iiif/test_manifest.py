import pytest

from papaya.iiif import SEARCH_API_1_CONTEXT, SEARCH_API_1_PROFILE, PRESENTATION_API_2_CONTEXT
from papaya.iiif.presentation import Manifest


def test_uris(papaya_context):
    manifest = Manifest(papaya_context, id='test')
    assert manifest.base_uri == 'http://example.com/manifests'
    assert manifest.uri == 'http://example.com/manifests/test/manifest'


def test_sequences(papaya_context):
    manifest = Manifest(papaya_context, id='test')
    assert len(manifest.sequences) == 1
    assert manifest.sequences[0].name == 'normal'


def test_find_sequence(papaya_context):
    manifest = Manifest(papaya_context, id='test')
    sequence = manifest.find_sequence('normal')
    assert sequence.name == 'normal'


def test_find_sequence_not_found(papaya_context):
    manifest = Manifest(papaya_context, id='test')
    with pytest.raises(KeyError):
        manifest.find_sequence('INVALID')


def test_find_canvas(papaya_context):
    manifest = Manifest(papaya_context, id='test')
    canvas = manifest.find_canvas('0')
    assert canvas.name == '0'
    assert canvas.uri == 'http://example.com/manifests/test/canvas/0'


def test_find_canvas_not_found(papaya_context):
    manifest = Manifest(papaya_context, id='test')
    with pytest.raises(KeyError):
        manifest.find_canvas('NOT_A_CANVAS')


def test_json(papaya_context):
    manifest = Manifest(papaya_context, id='test')
    json = manifest.json()
    assert json['@id'] == 'http://example.com/manifests/test/manifest'
    assert json['@type'] == 'sc:Manifest'
    assert json['label'] == 'Foobar'
    assert json['metadata'] == {}
    assert json['description'] == 'Testing manifest'
    assert len(json['sequences']) == 1
    assert json['service'] == []
    assert json['navDate'] == '2026-05-22'
    assert json['license'] == 'CC-BY-NC-SA'
    assert json['logo'] == {'@id': 'http://example.com/logo'}
    # context omitted
    assert '@context' not in json


def test_json_with_context(papaya_context):
    manifest = Manifest(papaya_context, id='test')
    json = manifest.json(with_context=True)
    assert json['@context'] == PRESENTATION_API_2_CONTEXT


def test_json_with_search_service(papaya_context):
    papaya_context.get_resource.return_value.is_searchable = True
    manifest = Manifest(papaya_context, id='test')
    json = manifest.json()
    assert json['service'] == [
        {
            '@context': SEARCH_API_1_CONTEXT,
            '@id': 'http://example.com/manifests/test/manifest/search',
            'profile': SEARCH_API_1_PROFILE,
        }
    ]
