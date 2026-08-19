from dataclasses import dataclass

from papaya.errors import IdentifierProblem, ManifestNotAvailable, ManifestNotFound, ServiceProblem
from papaya.iiif.image import ImageService
from papaya.iiif.presentation import Manifest
from papaya.source import SolrService, RepositoryService, IdentifierError, URLError, Resource, SolrDocumentNotFound, \
    SolrLookupError


@dataclass
class PapayaContext:
    """Configured service information for retrieving Solr documents
    and images, and generating manifests."""

    solr_service: SolrService
    repo_service: RepositoryService
    image_service: ImageService
    endpoint_url: str
    logo_url: str

    def get_resource_uri(self, iiif_id: str) -> str:
        try:
            return self.repo_service.get_resource_uri(iiif_id)
        except IdentifierError as e:
            raise IdentifierProblem(iiif_id=str(e)) from e

    def get_iiif_id(self, resource_uri: str) -> str:
        try:
            return self.repo_service.get_iiif_id(resource_uri)
        except URLError as e:
            raise ManifestNotAvailable(uri=resource_uri) from e

    def get_resource(self, manifest_id: str) -> Resource:
        try:
            return self.solr_service.get_resource(self.get_resource_uri(manifest_id))
        except SolrDocumentNotFound as e:
            raise ManifestNotFound(id=manifest_id) from e
        except SolrLookupError as e:
            raise ServiceProblem from e

    def get_manifest(self, manifest_id: str) -> Manifest:
        return Manifest(ctx=self, id=manifest_id)
