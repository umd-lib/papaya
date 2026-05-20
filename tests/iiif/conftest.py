from unittest.mock import MagicMock

import pytest

from papaya.context import PapayaContext
from papaya.iiif.image import ImageService
from papaya.source import SolrService, RepositoryService, Resource


@pytest.fixture
def papaya_context():
    ctx = MagicMock(
        spec=PapayaContext,
        solr_service=MagicMock(spec=SolrService),
        repo_service=MagicMock(spec=RepositoryService),
        image_service=MagicMock(
            spec=ImageService,
            thumbnail_width=250,
        ),
        endpoint_url='http://example.com/manifests',
        logo_url='http://example.com/logo',
    )
    ctx.get_resource.return_value = MagicMock(
        spec=Resource,
        label='Foobar',
        description='Testing manifest',
        metadata={},
        date='2026-05-22',
        license='CC-BY-NC-SA',
        page_uris=[
            'http://example.com/page1',
            'http://example.com/page2',
            'http://example.com/page3',
        ],
    )
    return ctx
