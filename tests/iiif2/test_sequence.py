from unittest.mock import MagicMock

import pytest

from papaya.iiif2 import Sequence, Manifest, PresentationContext, ImageService, PRESENTATION_API_CONTEXT
from papaya.source import SolrService, RepositoryService


@pytest.fixture
def presentation_context():
    return PresentationContext(
        solr_service=MagicMock(spec=SolrService),
        repo_service=MagicMock(spec=RepositoryService),
        image_service=MagicMock(spec=ImageService),
        endpoint_url='http://example.com/manifests',
        logo_url='http://example.com/logo',
    )


@pytest.fixture
def manifest(presentation_context) -> Manifest:
    return Manifest(ctx=presentation_context, id='test')


def test_sequence_json(manifest):
    sequence = Sequence(manifest=manifest, name='normal')
    json = sequence.json()
    assert json['@id'] == 'http://example.com/manifests/test/sequence/normal'
    assert json['@type'] == 'sc:Sequence'
    assert json['canvases'] == []
    # omit startCanvas (see LIBIIIF-230)
    assert 'startCanvas' not in json


def test_sequence_json_with_context(manifest):
    sequence = Sequence(manifest=manifest, name='normal')
    json = sequence.json(with_context=True)
    assert json['@context'] == PRESENTATION_API_CONTEXT
