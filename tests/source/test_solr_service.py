from unittest.mock import patch, MagicMock

import pysolr
import pytest

from papaya.source import SolrService, SolrLookupError, SolrDocumentNotFound, Resource


@pytest.fixture
def mock_solr():
    def _mock_solr(result_docs):
        mock_results = MagicMock(docs=result_docs)
        mock_results.__len__.return_value = len(result_docs)
        mock_solr = MagicMock()
        mock_solr.search.return_value = mock_results
        return mock_solr
    return _mock_solr


@patch('pysolr.Solr')
def test_get_doc(mock_solr_init, mock_solr, solr_doc, metadata_queries):
    mock_solr_init.return_value = mock_solr([solr_doc])
    service = SolrService(
        endpoint='http://example.com/foo',
        metadata_queries=metadata_queries,
        text_match_field='fulltext',
    )
    assert service.get_doc('http://example.com/fcrepo/123') == solr_doc


@patch('pysolr.Solr')
def test_get_doc_too_many_documents(mock_solr_init, mock_solr, solr_doc, metadata_queries):
    mock_solr_init.return_value = mock_solr([solr_doc, solr_doc, solr_doc])
    service = SolrService(
        endpoint='http://example.com/foo',
        metadata_queries=metadata_queries,
        text_match_field='fulltext',
    )
    with pytest.raises(SolrLookupError):
        service.get_doc('http://example.com/fcrepo/123')


@patch('pysolr.Solr')
def test_get_doc_document_not_found(mock_solr_init, mock_solr, solr_doc, metadata_queries):
    mock_solr_init.return_value = mock_solr([])
    service = SolrService(
        endpoint='http://example.com/foo',
        metadata_queries=metadata_queries,
        text_match_field='fulltext',
    )
    with pytest.raises(SolrDocumentNotFound):
        service.get_doc('http://example.com/fcrepo/123')


@patch('pysolr.Solr')
def test_get_doc_solr_error(mock_solr_init, solr_doc, metadata_queries):
    mock_solr = MagicMock()
    mock_solr.search.side_effect = pysolr.SolrError
    mock_solr_init.return_value = mock_solr
    service = SolrService(
        endpoint='http://example.com/foo',
        metadata_queries=metadata_queries,
        text_match_field='fulltext',
    )
    with pytest.raises(SolrLookupError):
        service.get_doc('http://example.com/fcrepo/123')


@patch('pysolr.Solr')
def test_get_resource(mock_solr_init, mock_solr, solr_doc, metadata_queries):
    mock_solr_init.return_value = mock_solr([solr_doc])
    service = SolrService(
        endpoint='http://example.com/foo',
        metadata_queries=metadata_queries,
        text_match_field='fulltext',
    )
    resource = service.get_resource('http://example.com/fcrepo/123')
    assert isinstance(resource, Resource)
    assert resource.uri == 'http://example.com/fcrepo/123'
