import pytest

from papaya.iiif import PRESENTATION_API_2_CONTEXT
from papaya.iiif.presentation import Manifest, Sequence


@pytest.fixture
def manifest(papaya_context) -> Manifest:
    return Manifest(ctx=papaya_context, id='test')


def test_uri(manifest):
    sequence = Sequence(manifest=manifest, name='normal')
    assert sequence.uri == 'http://example.com/manifests/test/sequence/normal'


def test_canvases(manifest):
    sequence = Sequence(manifest=manifest, name='normal')
    canvases = sequence.canvases
    assert len(canvases) == 3
    assert canvases[0].name == '0'
    assert canvases[0].uri == 'http://example.com/manifests/test/canvas/0'
    assert canvases[1].name == '1'
    assert canvases[1].uri == 'http://example.com/manifests/test/canvas/1'
    assert canvases[2].name == '2'
    assert canvases[2].uri == 'http://example.com/manifests/test/canvas/2'


def test_get_canvas(manifest):
    sequence = Sequence(manifest=manifest, name='normal')
    canvas = sequence.get_canvas('0')
    assert canvas.name == '0'
    assert canvas.uri == 'http://example.com/manifests/test/canvas/0'


def test_get_canvas_not_found(manifest):
    sequence = Sequence(manifest=manifest, name='normal')
    with pytest.raises(KeyError):
        sequence.get_canvas('NOT_A_CANVAS')


def test_sequence_json(manifest):
    sequence = Sequence(manifest=manifest, name='normal')
    json = sequence.json()
    assert json['@id'] == 'http://example.com/manifests/test/sequence/normal'
    assert json['@type'] == 'sc:Sequence'
    assert len(json['canvases']) == 3
    # omit startCanvas (see LIBIIIF-230)
    assert 'startCanvas' not in json


def test_sequence_json_with_context(manifest):
    sequence = Sequence(manifest=manifest, name='normal')
    json = sequence.json(with_context=True)
    assert json['@context'] == PRESENTATION_API_2_CONTEXT
