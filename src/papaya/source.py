"""
## Metadata Queries

Metadata queries whose keys begin with `$` are used to define the
structure and basic manifest metadata:

* **`$uri`** Returns the resource URI
* **`$label`** Returns the value to use as the manifest `label`. If there
  are multiple values (e.g., multiple languages), concatenates them using
  the string `' / '`
* **`$date`** Returns the value to use as the manifest `navDate`
* **`$license_uri`** Returns URI to use as the manifest `license`
* **`$description`** Returns the value to use as the manifest `description`
  If there are multiple values (e.g., multiple languages), concatenates
  them using the string `' / '`
* **`$page_uris`** Returns a list of page URIs in page order
* **`$page_image_ids`** Returns a list of IIIF Image IDs for the pages,
  in the same order as the `$page_uris`

Metadata queries whose keys begin with `$*` all take arguments at
runtime:

* **`$*page_doc`**  Given a page URI as `$uri`, return that page's
  document
* **`$*page_label`** Given a page URI as `$uri`, return the value to
  use as the `canvas` label
* **`$*file_page_uri`** Given a file URI as `$uri`, return the URI of
  the page that file belongs to

Any metadata queries whose keys do not begin with a `$` will be used
to populate the `metadata` mapping in the manifest. The key becomes the
`label` and the result of the query becomes the `value`. For example:

```yaml
Title: .object__title__display[]?
Date: .object__date__edtf
Subject: .object__subject[]?.subject__label__display[]?
```

Combined with this resource document:

```json
{
    "object__title__display": ["Foobar"],
    "object__date__edtf": "1992/2001",
    "object__subject": [
        {"subject__label__display": ["Science", "[@de]Wissenschaft"]}
    ]
}
```

Would yield this metadata mapping in the output manifest:

```json
{
    "metadata": [
        {"label": "Title", "value": ["Foobar"]},
        {"label": "Date", "value": "1992/2001"},
        {
            "label": "Subject", "value": [
                "Science",
                {"@language": "de", "@value": "Wissenschaft"}
            ]
        }
    ]
}
```
"""

import logging
import re
from collections.abc import Mapping
from typing import NamedTuple, Any
from urllib.parse import parse_qsl
from uuid import uuid4

import jq
import pysolr
from jq import _Program, _ProgramWithInput  # noqa

logger = logging.getLogger(__name__)


def format_value(value: str) -> dict[str, str] | str:
    """If the given `value` starts with a language tag `[@{language}]`
    (e.g., `[@de]` or `[@ja-latn]`, extracts the language from the tag
    and returns a JSON-LD-style dictionary with `@language` and `@value`
    keys. Otherwise, just returns the unmodified `value`."""
    if m := re.match(r'\[@(.*?)](.*)', value):
        return {'@language': m[1], '@value': m[2]}
    else:
        return value


class RepositoryService:
    """Service for translating between repository URIs and IIIF IDs

    ```pycon
    >>> repo_service = RepositoryService(endpoint='http://example.com/repo', prefix='fcrepo:')

    >>> repo_service.get_iiif_id('http://example.com/repo/foo/bar/123')
    'fcrepo:foo:bar:123'

    >>> repo_service.get_resource_uri('fcrepo:other:resource:5:678')
    'http://example.com/repo/other/resource/5/678'

    ```
    """

    def __init__(self, endpoint: str, prefix: str, path_sep: str = ':'):
        self.endpoint = endpoint
        """Base URL of the source repository."""
        self.prefix = prefix
        """Prefix string used in the IIIF IDs."""
        self.path_sep = path_sep
        """Character to replace the `'/'` path separator when converting from URI
        to IIIF ID, and to convert to `'/'` when going the other way. Defaults to
        `':'`."""

    def get_resource_uri(self, iiif_id: str) -> str:
        """Converts a IIIF ID to a repository URI.

        If the `iiif_id` does not start with the `prefix`, raises an
        `IdentifierError` exception."""
        if not iiif_id.startswith(self.prefix):
            logger.error(f'Invalid IIIF ID: Expecting "{self.prefix}<local part>", got "{iiif_id}"')
            raise IdentifierError(iiif_id)
        local_part = iiif_id.removeprefix(self.prefix)
        repo_path = '/' + local_part.replace(self.path_sep, '/')
        return self.endpoint + repo_path

    def get_iiif_id(self, resource_uri: str) -> str:
        """Converts a repository URI to a IIIF ID.

        If the `resource_uri` does not start with the `endpoint`, raises a
        `URLError` exception."""
        if not resource_uri.startswith(self.endpoint):
            logger.error(f'{resource_uri} not part of configured repository {self.endpoint}')
            raise URLError(resource_uri)
        return resource_uri.replace(f'{self.endpoint}/', self.prefix).replace('/', self.path_sep)


class IdentifierError(ValueError):
    """There was a problem with a IIIF ID."""


class URLError(ValueError):
    """There was a problem with a resource URI."""


class Resource:
    """A digital object that has a IIIF manifest."""

    def __init__(self, doc: Mapping[str, Any], metadata_queries: Mapping[str, str] = None):
        self.doc = doc
        """Mapping of digital object metadata. Typically a Solr document."""
        self.metadata_queries = metadata_queries or {}
        """Mapping of short keys to `jq` expressions. Used for constructing
        the metadata and structure of the IIIF manifest. See
        [Metadata Queries](#metadata-queries) for more details and a list of
        expected keys."""
        self._jq_programs: dict[str, _Program] = {
            k: jq.compile(v) for k, v in self.metadata_queries.items() if not k.startswith('$*')
        }

    def _query(self, key: str) -> _ProgramWithInput:
        return self._jq_programs[key].input_value(self.doc)

    @property
    def uri(self) -> str:
        """URI of the digital object. Metadata query key: `$uri`"""
        return self._query('$uri').first()

    @property
    def label(self) -> str:
        """Label for the manifest. Metadata query key: `$label`

        The query may return multiple values. All values are concatenated
        using the string `' / '`."""
        return ' / '.join(self._query('$label'))

    @property
    def page_uris(self) -> list[str]:
        """List of URIs of the individual pages of the digital object.
        Metadata query key: `$page_uris`

        These should be in the desired presentation order."""
        return self._query('$page_uris').all()

    @property
    def date(self) -> str:
        """Navigation date (`navDate`) for the manifest. Metadata query
        key: `$date`"""
        return self._query('$date').first()

    @property
    def license(self) -> str:
        """License URL for the manifest. Metadata query key: `$license_uri`"""
        return self._query('$license_uri').first()

    @property
    def description(self) -> str:
        """Description for the manifest. Metadata query key: `$description`

        The query may return multiple values. All values are concatenated
        using the string `' / '`."""
        return ' / '.join(self._query('$description'))

    @property
    def metadata(self) -> list[dict]:
        """Descriptive metadata for the manifest.

        Any key in the `metadata_queries` mapping that does not start with `$`
        is assumed to be descriptive metadata. They key becomes the label for
        the field, and the returned value or values from the query are processed
        by `format_language_tag` and become the value of the field."""
        keys = [k for k in self.metadata_queries.keys() if not k.startswith('$')]
        metadata = [{'label': k, 'value': [format_value(v) for v in self._query(k) if v is not None]} for k in keys]
        return [m for m in metadata if m['value']]

    def index(self, page_uri: str) -> int:
        """Given a page URI, return the (0-based) index of that page in the
        sequential list of `page_uris`"""
        return self.page_uris.index(page_uri)

    def get_page_doc(self, page_uri: str) -> dict:
        """Given a page URI, returns the mapping of metadata of that single page.
        Metadata query key: `$*page_doc`. The given `page_uri` is passed to the
        query as the `$uri` argument."""
        program: _Program = jq.compile(self.metadata_queries['$*page_doc'], args={'uri': page_uri})
        return program.input_value(self.doc).first()

    def find_page_doc(self, file_uri: str) -> dict:
        """Given a file URI, returns the mapping of metadata of the single page
        that contains that file. Metadata query key: `$*file_page_uri`. The given
        `file_uri` is passed to the query as the `$uri` argument."""
        program: _Program = jq.compile(self.metadata_queries['$*file_page_uri'], args={'uri': file_uri})
        return program.input_value(self.doc).first()

    def get_page_image_id(self, page_uri: str) -> str:
        """Given a page URI, returns the IIIF ID of the image that should be
        displayed on that page. Metadata query key: `$page_image_ids`. The
        given `page_uri` is passed to the query as the `$uri` argument."""
        return self._query('$page_image_ids').all()[self.index(page_uri)]

    def get_page_label(self, page_uri: str) -> str:
        """Given a page URI, returns the value to use as the label for that page.
        Metadata query key: `$*page_label`. The given `page_uri` is passed to the
        query as the `$uri` argument."""
        program: _Program = jq.compile(self.metadata_queries['$*page_label'], args={'uri': page_uri})
        return program.input_value(self.doc).first()


class SolrLookupError(Exception):
    """There was a problem retrieving the Solr document from the server."""


class SolrDocumentNotFound(SolrLookupError):
    """No Solr document matching the given search was found."""


class SolrService:
    """Service for querying a Solr server to retrieve digital object metadata
    to use to build the IIIF manifest."""

    def __init__(
        self, endpoint: str, metadata_queries: Mapping[str, str], text_match_field: str, uri_field: str = 'id'
    ):
        self.endpoint = endpoint
        """URL of the Solr core to use. Must have a '/select' query handler."""
        self.metadata_queries = metadata_queries
        """Mapping of short keys to `jq` expressions. Used for constructing
        the metadata and structure of the IIIF manifest. See
        [Metadata Queries](#metadata-queries) for more details and a list of
        expected keys."""
        self.text_match_field = text_match_field
        """Name of the Solr field containing tagged text data."""
        self.uri_field = uri_field
        """Name of the Solr field containing the resource URI. Defaults to `'id'`."""

        self._solr = pysolr.Solr(self.endpoint)

    def get_doc(self, resource_uri: str) -> dict:
        """Retrieve the Solr document whose `uri_field` value matches the given `resource_uri`.

        If no document is found, raises a `SolrDocumentNotFound` exception. If more
        than one document is found, or there is some other error sending the request
        to Solr, raises a `SolrLookupError` exception."""
        try:
            # use the term query parser and pass the URI as a regular query parameter
            # so that Solr itself will handle the escaping of the URI value
            results = self._solr.search(q=f'{{!term f={self.uri_field} v=$id}}', id=resource_uri)
        except pysolr.SolrError as e:
            raise SolrLookupError(str(e)) from e

        if len(results) == 0:
            raise SolrDocumentNotFound(f'No document with id "{resource_uri}" found')
        if len(results) > 1:
            raise SolrLookupError(f'Multiple documents with id "{resource_uri}" found')

        return results.docs[0]

    def get_resource(self, resource_uri: str) -> Resource:
        """Get the `Resource` object representing the given `resource_uri`."""
        return Resource(self.get_doc(resource_uri), self.metadata_queries)

    def get_text_matches(self, resource_uri: str, text_query: str, index: int = None) -> list[TaggedText]:
        """Search the `text_match_field` of the resource with the given `resource_uri`
        for occurrences of `text_query`, using Solr's highlighting capabilities. Returns
        a list of `TaggedText` objects that represent each instance that matched.

        If `index` is given, limit the results to only those on the page with that `index`."""

        # use a unique match tag to mark the parts of the snippets
        # we want to extract into annotations
        match_tag = f'<<{uuid4()}>>'
        try:
            results = self._solr.search(
                q=f'{{!term f={self.uri_field} v=$id}}',
                id=resource_uri,
                hl='on',
                **{
                    'hl.fl': self.text_match_field,
                    'hl.q': f'{self.text_match_field}:{text_query}',
                    'hl.snippets': 100,
                    'hl.fragsize': 50,
                    'hl.maxAnalyzedChars': 1_000_000,
                    'hl.tag.pre': match_tag,
                    'hl.tag.post': match_tag,
                },
            )
        except pysolr.SolrError as e:
            raise SolrLookupError(str(e)) from e

        hits = []
        for text in results.highlighting[resource_uri].get(self.text_match_field, []):
            hits.extend(TaggedText.parse(x) for i, x in enumerate(text.split(match_tag)) if i % 2 == 1)

        if index is not None:
            return [h for h in hits if int(h.params['n']) == index]
        else:
            return hits


class TaggedText(NamedTuple):
    text: str
    """Text of a token"""
    params: dict[str, Any]
    """Parameters mapping from the token"""

    @classmethod
    def parse(cls, dps_string: str):
        """Splits `dps_string` using `|`. The first part becomes the `text`,
        and the second part is parsed as an HTTP query string and becomes
        the `params` dictionary."""
        text, tag = dps_string.split('|', 1)
        return cls(
            text=text,
            params=dict(parse_qsl(tag)),
        )
