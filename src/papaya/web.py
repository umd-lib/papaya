import logging
import os
from http import HTTPStatus

from configurenv import load_config_from_files
from flask import Flask, url_for, redirect, request
from werkzeug.exceptions import InternalServerError

from papaya import __version__
from papaya.errors import ProblemDetailError, problem_detail_response, IdentifierProblem, ManifestNotFound, \
    SequenceNotFound, CanvasNotFound, AnnotationNotFound, ServiceProblem
from papaya.iiif2 import ImageService, Manifest, DEFAULT_THUMBNAIL_WIDTH
from papaya.source import RepositoryService, SolrService, URLError, IdentifierError, SolrDocumentNotFound, \
    SolrLookupError

debug_mode = int(os.environ.get('FLASK_DEBUG', '0'))
logging.basicConfig(
    level='DEBUG' if debug_mode else 'INFO',
    format='%(levelname)s:%(threadName)s:%(name)s:%(message)s',
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config.from_prefixed_env('PAPAYA')
    load_config_from_files(app.config)

    app.logger.info(f'papaya/{__version__}')
    app.logger.debug(app.config)

    solr_service = SolrService(
        endpoint=app.config['SOLR_ENDPOINT'],
        metadata_queries=app.config.get('METADATA_QUERIES', {}),
    )
    repo_service = RepositoryService(
        endpoint=app.config['FCREPO_ENDPOINT'],
        prefix=app.config['FCREPO_PREFIX'],
    )
    image_service = ImageService(
        endpoint=app.config['IIIF_IMAGE_ENDPOINT'],
        thumbnail_width=app.config.get('THUMBNAIL_WIDTH', DEFAULT_THUMBNAIL_WIDTH)
    )

    def get_resource_uri(iiif_id: str) -> str:
        try:
            return repo_service.get_resource_uri(iiif_id)
        except IdentifierError as e:
            raise IdentifierProblem(iiif_id=str(e)) from e

    def get_iiif_id(resource_uri: str) -> str:
        try:
            return repo_service.get_iiif_id(resource_uri)
        except URLError as e:
            raise InternalServerError from e

    def get_resource(manifest_id: str):
        try:
            return solr_service.get_resource(get_resource_uri(manifest_id))
        except SolrDocumentNotFound as e:
            raise ManifestNotFound(id=manifest_id) from e
        except SolrLookupError as e:
            raise ServiceProblem from e

    def get_manifest_object(manifest_id: str):
        resource = get_resource(manifest_id)
        manifest_url = url_for('get_manifest', manifest_id=manifest_id, _external=True)
        return Manifest(
            base_uri=manifest_url[:-9],
            resource=resource,
            image_service=image_service,
            logo_url=app.config.get('LOGO_URL', None)
        )

    @app.route('/', methods=['GET'])
    def root():
        """Provides a basic form to generate a IIIF manifest from a resource URL."""
        return f'''
        <html>
          <head>
            <title>Papaya</title>
          </head>
          <body>
            <h1>Papaya</h1>
            <form method="post" action="">
              <label>URI: <input name="uri" type="text" size="80"/></label><button type="submit">Submit</button>
            </form>
            <hr/>
            <p id="version">{__version__}</p>
          </body>
        </html>
        '''

    @app.route('/', methods=['POST'])
    def find_manifest():
        """Redirects to the actual manifest URL using the resource URL submitted
        via the form."""
        uri = request.form['uri']
        return redirect(url_for('get_manifest', manifest_id=get_iiif_id(uri), _external=True), HTTPStatus.FOUND)

    @app.route('/manifests/<manifest_id>/')
    @app.route('/manifests/<manifest_id>/manifest.json')
    def redirect_to_manifest(manifest_id: str):
        """Redirects requests for the manifest to its canonical URL."""
        return redirect(url_for('get_manifest', manifest_id=manifest_id, _external=True), HTTPStatus.MOVED_PERMANENTLY)

    @app.route('/manifests/<manifest_id>/manifest')
    def get_manifest(manifest_id: str):
        """Implements the manifest response.

        See also: https://iiif.io/api/presentation/2.1/#manifest"""
        return get_manifest_object(manifest_id).to_dict(with_context=True)

    @app.route('/manifests/<manifest_id>/sequence/<sequence_name>')
    def get_sequence(manifest_id: str, sequence_name: str):
        """Implements the sequence response.

        See also: https://iiif.io/api/presentation/2.1/#sequence"""
        try:
            return get_manifest_object(manifest_id).find_sequence(sequence_name).to_dict(with_context=True)
        except KeyError as e:
            raise SequenceNotFound(sequence_name=sequence_name, manifest_id=manifest_id) from e

    @app.route('/manifests/<manifest_id>/canvas/<canvas_name>')
    def get_canvas(manifest_id: str, canvas_name: str):
        """Implements the canvas response.

        See also: https://iiif.io/api/presentation/2.1/#canvas"""
        try:
            return get_manifest_object(manifest_id).find_canvas(canvas_name).to_dict(with_context=True)
        except KeyError as e:
            raise CanvasNotFound(canvas_name=canvas_name, manifest_id=manifest_id) from e

    @app.route('/manifests/<manifest_id>/annotation/<annotation_name>')
    def get_annotation(manifest_id: str, annotation_name: str):
        """Implements the image resource response.

        See also: https://iiif.io/api/presentation/2.1/#image-resources"""
        try:
            return get_manifest_object(manifest_id).find_annotation(annotation_name).to_dict(with_context=True)
        except KeyError as e:
            raise AnnotationNotFound(annotation_name=annotation_name, manifest_id=manifest_id) from e

    app.register_error_handler(ProblemDetailError, problem_detail_response)

    return app


