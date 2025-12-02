import logging
import os
from http import HTTPStatus
from urllib.parse import urlencode

from configurenv import load_config_from_files
from flask import Flask, url_for, redirect, request

from papaya import __version__
from papaya.errors import (
    ProblemDetailError,
    problem_detail_response,
    SequenceNotFound,
    CanvasNotFound,
    AnnotationNotFound,
)
from papaya.iiif2 import ImageService, DEFAULT_THUMBNAIL_WIDTH, PresentationContext, SearchHitsList
from papaya.source import RepositoryService, SolrService

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

    ctx = PresentationContext(
        solr_service=SolrService(
            endpoint=app.config['SOLR_ENDPOINT'],
            metadata_queries=app.config.get('METADATA_QUERIES', {}),
            text_match_field=app.config['SOLR_TEXT_MATCH_FIELD'],
        ),
        repo_service=RepositoryService(
            endpoint=app.config['FCREPO_ENDPOINT'],
            prefix=app.config['FCREPO_PREFIX'],
        ),
        image_service=ImageService(
            endpoint=app.config['IIIF_IMAGE_ENDPOINT'],
            thumbnail_width=app.config.get('THUMBNAIL_WIDTH', DEFAULT_THUMBNAIL_WIDTH),
        ),
        endpoint_url=app.config['URL'],
        logo_url=app.config.get('LOGO_URL', None),
    )

    @app.route('/')
    def root():
        return redirect(url_for('manifests_form'), HTTPStatus.FOUND)

    @app.route('/manifests/', methods=['GET'])
    def manifests_form():
        """Provides a basic form to generate a IIIF manifest from a resource URL."""
        return f"""
        <html>
          <head>
            <title>Papaya</title>
          </head>
          <body>
            <h1>Papaya</h1>
            <form method="post" action="">
              <label>URI: <input name="uri" type="text" size="80"/></label>
              <label>Text query: <input name="text_query" type="text"/></label>
              <button type="submit">Submit</button>
            </form>
            <hr/>
            <p id="version">{__version__}</p>
          </body>
        </html>
        """

    @app.route('/manifests/', methods=['POST'])
    def find_manifest():
        """Redirects to the actual manifest URL using the resource URL submitted
        via the form."""
        url = url_for('get_manifest', manifest_id=ctx.get_iiif_id(request.form['uri']), _external=True)
        if text_query := request.form.get('text_query', None):
            url += f'?{urlencode({"q": text_query})}'
        return redirect(url, HTTPStatus.FOUND)

    @app.route('/manifests/<manifest_id>/')
    @app.route('/manifests/<manifest_id>/manifest.json')
    def redirect_to_manifest(manifest_id: str):
        """Redirects requests for the manifest to its canonical URL."""
        return redirect(url_for('get_manifest', manifest_id=manifest_id), HTTPStatus.MOVED_PERMANENTLY)

    @app.route('/manifests/<manifest_id>/manifest')
    def get_manifest(manifest_id: str):
        """Implements the manifest response.

        See also: https://iiif.io/api/presentation/2.1/#manifest"""
        return ctx.get_manifest(manifest_id, request.args.get('q', None)).json(with_context=True)

    @app.route('/manifests/<manifest_id>/sequence/<sequence_name>')
    def get_sequence(manifest_id: str, sequence_name: str):
        """Implements the sequence response.

        See also: https://iiif.io/api/presentation/2.1/#sequence"""
        try:
            manifest = ctx.get_manifest(manifest_id, request.args.get('q', None))
            return manifest.find_sequence(sequence_name).json(with_context=True)
        except KeyError as e:
            raise SequenceNotFound(sequence_name=sequence_name, manifest_id=manifest_id) from e

    @app.route('/manifests/<manifest_id>/canvas/<canvas_name>')
    def get_canvas(manifest_id: str, canvas_name: str):
        """Implements the canvas response.

        See also: https://iiif.io/api/presentation/2.1/#canvas"""
        try:
            manifest = ctx.get_manifest(manifest_id, request.args.get('q', None))
            return manifest.find_canvas(canvas_name).json(with_context=True)
        except KeyError as e:
            raise CanvasNotFound(canvas_name=canvas_name, manifest_id=manifest_id) from e

    @app.route('/manifests/<manifest_id>/annotation/<annotation_name>')
    def get_annotation(manifest_id: str, annotation_name: str):
        """Implements the image resource response.

        See also: https://iiif.io/api/presentation/2.1/#image-resources"""
        try:
            return ctx.get_manifest(manifest_id).find_annotation(annotation_name).json(with_context=True)
        except KeyError as e:
            raise AnnotationNotFound(annotation_name=annotation_name, manifest_id=manifest_id) from e

    @app.route('/manifests/<manifest_id>/list/<canvas_name>-search')
    def get_annotation_list(manifest_id: str, canvas_name: str):
        try:
            canvas = ctx.get_manifest(manifest_id).find_canvas(canvas_name)
        except KeyError as e:
            raise CanvasNotFound(canvas_name=canvas_name, manifest_id=manifest_id) from e

        return SearchHitsList(canvas, request.args.get('q')).json(with_context=True)

    app.register_error_handler(ProblemDetailError, problem_detail_response)

    return app
