from unittest.mock import MagicMock

import pytest

from papaya.iiif import PRESENTATION_API_2_CONTEXT
from papaya.iiif.presentation import Manifest, Canvas
from papaya.iiif.search import SearchResultsList, SearchResult, SearchResultContext
from papaya.source import SolrHit, TaggedText


@pytest.fixture
def solr_hits() -> list[SolrHit]:
    return [
        SolrHit(
            id='qwerty',
            tokens_before=[
                TaggedText('The', {'n': 0, 'xywh': '0,0,1,1'}),
                TaggedText('Empire', {'n': 0, 'xywh': '1,1,1,1'}),
            ],
            match=TaggedText('Strikes', {'n': 0, 'xywh': '2,2,1,1'}),
            tokens_after=[
                TaggedText('Back', {'n': 0, 'xywh': '3,3,1,1'}),
            ],
        ),
    ]


@pytest.fixture
def manifest(solr_hits) -> Manifest:
    mock_manifest = MagicMock(
        spec=Manifest,
        id='foo',
        base_uri='http://iiif.example.com',
        uri='http://iiif.example.com/foo/manifest',
    )
    mock_manifest.search_text.return_value = solr_hits
    return mock_manifest


@pytest.fixture
def canvas(manifest, solr_hits) -> Canvas:
    mock_canvas = MagicMock(
        spec=Canvas,
        manifest=manifest,
        uri=f'{manifest.base_uri}/{manifest.id}/canvas/0',
        name='0',
    )
    mock_canvas.search_text.return_value = solr_hits
    return mock_canvas


@pytest.mark.parametrize(
    ('query', 'expected_uri'),
    [
        ('bar', 'http://iiif.example.com/foo/manifest/search?q=bar'),
        ('10%', 'http://iiif.example.com/foo/manifest/search?q=10%25'),
        ('pony express', 'http://iiif.example.com/foo/manifest/search?q=pony+express'),
    ]
)
def test_uri_for_manifest(manifest, query, expected_uri):
    results = SearchResultsList(manifest, query)
    assert results.uri == expected_uri


def test_search_hits_on_manifest(manifest):
    results = SearchResultsList(manifest, 'strike')
    assert len(results.search_hits) == 1


def test_result_annotations_on_manifest(manifest):
    results = SearchResultsList(manifest, 'strike')
    assert len(results.result_annotations) == 1
    annotation = results.result_annotations[0]
    assert isinstance(annotation, SearchResult)
    assert annotation.hit.match.text == 'Strikes'
    assert annotation.hit.before == 'The Empire'
    assert annotation.hit.after == 'Back'


def test_context_annotations_on_manifest(manifest):
    results = SearchResultsList(manifest, 'strike')
    assert len(results.context_annotations) == 1
    annotation = results.context_annotations[0]
    assert isinstance(annotation, SearchResultContext)


def test_json_for_manifest(manifest):
    results = SearchResultsList(manifest, 'strike')
    json = results.json()
    assert json['@id'] == 'http://iiif.example.com/foo/manifest/search?q=strike'
    assert json['@type'] == 'sc:AnnotationList'
    assert len(json['resources']) == 1
    assert len(json['hits']) == 1
    assert '@context' not in json


def test_json_for_manifest_with_context(manifest):
    results = SearchResultsList(manifest, 'strike')
    json = results.json(with_context=True)
    assert json['@context'] == PRESENTATION_API_2_CONTEXT


@pytest.mark.parametrize(
    ('query', 'expected_uri'),
    [
        ('bar', 'http://iiif.example.com/foo/canvas/0/search?q=bar'),
        ('10%', 'http://iiif.example.com/foo/canvas/0/search?q=10%25'),
        ('pony express', 'http://iiif.example.com/foo/canvas/0/search?q=pony+express'),
    ]
)
def test_uri_for_canvas(canvas, query, expected_uri):
    results = SearchResultsList(canvas, query)
    assert results.uri == expected_uri


def test_search_hits_on_canvas(canvas):
    results = SearchResultsList(canvas, 'strike')
    assert len(results.search_hits) == 1


def test_result_annotations_on_canvas(canvas):
    results = SearchResultsList(canvas, 'strike')
    assert len(results.result_annotations) == 1
    annotation = results.result_annotations[0]
    assert isinstance(annotation, SearchResult)
    assert annotation.hit.match.text == 'Strikes'
    assert annotation.hit.before == 'The Empire'
    assert annotation.hit.after == 'Back'


def test_context_annotations_on_canvas(canvas):
    results = SearchResultsList(canvas, 'strike')
    assert len(results.context_annotations) == 1
    annotation = results.context_annotations[0]
    assert isinstance(annotation, SearchResultContext)
