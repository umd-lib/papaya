import logging
import re
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from codetiming import Timer
from configurenv import load_config_from_files
from flask import Flask, url_for, redirect, request

from papaya import __version__
from papaya.context import PapayaContext
from papaya.errors import ProblemDetailError, problem_detail_response, SequenceNotFound, CanvasNotFound, \
    AnnotationNotFound, MissingQueryParameter
from papaya.iiif import DEFAULT_THUMBNAIL_WIDTH, DEFAULT_UNAVAILABLE_IMAGE_ID
from papaya.iiif.image import ImageService
from papaya.iiif.search import SearchResultsList
from papaya.source import RepositoryService, SolrService


def get_log_level(config: Mapping[str, Any]) -> str:
    if int(config.get('DEBUG', '0')):
        return 'DEBUG'
    elif 'LOG_LEVEL' in config:
        return config['LOG_LEVEL']
    else:
        return 'INFO'


def configure_logging(app: Flask):
    logging.basicConfig(
        level=get_log_level(app.config),
        format='%(levelname)s:%(threadName)s:%(name)s:%(message)s',
    )


def expand_shortened_path(path: str) -> str:
    """Expand a `path` string containing a shortened IIIF ID. If there is no shortened
    IIIF ID in `path`, returns the original string.

    ```pycon
    >>> expand_shortened_path('/manifests/fcrepo:dc:2021:2::d48c8493-c226-4f17-9990-52bd552c2cc6')
    '/manifests/fcrepo:dc:2021:2:d4:8c:84:93:d48c8493-c226-4f17-9990-52bd552c2cc6'

    # not shortened
    >>> expand_shortened_path('/manifests/fcrepo:dc:2021:2:d4:8c:84:93:d48c8493-c226-4f17-9990-52bd552c2cc6')
    '/manifests/fcrepo:dc:2021:2:d4:8c:84:93:d48c8493-c226-4f17-9990-52bd552c2cc6'

    ```
    """
    if not (m := re.search(r'::([0-9a-f]{8})', path)):
        return path
    uuid_segment = m[1]
    pairtree = ':'.join(uuid_segment[n:n + 2] for n in range(0, 8, 2))
    # insert the pairtree
    return path[:m.span()[0]] + f':{pairtree}:{m[1]}' + path[m.span()[1]:]


def create_app():
    app = Flask(__name__)
    app.config.from_prefixed_env('PAPAYA')
    load_config_from_files(app.config)
    configure_logging(app)

    # store the application context in the app config, so the unit tests
    # can easily inject a mock context when needed
    app.config['papaya_context'] = PapayaContext(
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
            origin=app.config.get('IIIF_IMAGE_ORIGIN', None),
            thumbnail_width=app.config.get('THUMBNAIL_WIDTH', DEFAULT_THUMBNAIL_WIDTH),
            unavailable_image_id=app.config.get('UNAVILABLE_IMAGE_ID', DEFAULT_UNAVAILABLE_IMAGE_ID),
        ),
        endpoint_url=app.config['URL'],
        logo_url=app.config.get('LOGO_URL', None),
    )

    app.logger.info(f'papaya/{__version__}')
    app.logger.debug(app.config)

    @app.before_request
    def rewrite_short_ids():
        """Rewrite abbreviated IIIF IDs to their full form."""
        new_path = expand_shortened_path(request.path)
        return redirect(new_path, code=HTTPStatus.PERMANENT_REDIRECT) if new_path != request.path else None

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
        ctx = app.config['papaya_context']
        url = url_for('get_manifest', manifest_id=ctx.get_iiif_id(request.form['uri']))
        return redirect(url, HTTPStatus.FOUND)

    @app.route('/manifests/<manifest_id>/')
    @app.route('/manifests/<manifest_id>/manifest.json')
    def redirect_to_manifest(manifest_id: str):
        """Redirects requests for the manifest to its canonical URL."""
        url = url_for('get_manifest', manifest_id=manifest_id)
        if request.query_string:
            url += f'?{request.query_string.decode()}'
        return redirect(url, HTTPStatus.MOVED_PERMANENTLY)

    @app.route('/manifests/<manifest_id>/manifest')
    def get_manifest(manifest_id: str):
        """Implements the manifest response.

        See also: https://iiif.io/api/presentation/2.1/#manifest"""
        with Timer(
            name=f'retrieve manifest for {manifest_id}',
            text='Time to {name}: {milliseconds:.3f} ms',
            logger=app.logger.info,
        ):
            ctx = app.config['papaya_context']
            return ctx.get_manifest(manifest_id).json(with_context=True)

    @app.route('/manifests/<manifest_id>/sequence/<sequence_name>')
    def get_sequence(manifest_id: str, sequence_name: str):
        """Implements the sequence response.

        See also: https://iiif.io/api/presentation/2.1/#sequence"""
        with Timer(
            name=f'retrieve sequence {sequence_name} in {manifest_id}',
            text='Time to {name}: {milliseconds:.3f} ms',
            logger=app.logger.info,
        ):
            ctx = app.config['papaya_context']
            try:
                manifest = ctx.get_manifest(manifest_id)
                return manifest.get_sequence(sequence_name).json(with_context=True)
            except KeyError as e:
                raise SequenceNotFound(sequence_name=sequence_name, manifest_id=manifest_id) from e

    @app.route('/manifests/<manifest_id>/canvas/<canvas_name>')
    def get_canvas(manifest_id: str, canvas_name: str):
        """Implements the canvas response.

        See also: https://iiif.io/api/presentation/2.1/#canvas"""
        with Timer(
            name=f'retrieve canvas {canvas_name} in {manifest_id}',
            text='Time to {name}: {milliseconds:.3f} ms',
            logger=app.logger.info,
        ):
            ctx = app.config['papaya_context']
            try:
                manifest = ctx.get_manifest(manifest_id)
                return manifest.find_canvas(canvas_name).json(with_context=True)
            except KeyError as e:
                raise CanvasNotFound(canvas_name=canvas_name, manifest_id=manifest_id) from e

    @app.route('/manifests/<manifest_id>/annotation/<annotation_name>')
    def get_annotation(manifest_id: str, annotation_name: str):
        """Implements the image resource response.

        See also: https://iiif.io/api/presentation/2.1/#image-resources"""
        with Timer(
            name=f'retrieve annotation {annotation_name} in {manifest_id}',
            text='Time to {name}: {milliseconds:.3f} ms',
            logger=app.logger.info,
        ):
            ctx = app.config['papaya_context']
            try:
                return ctx.get_manifest(manifest_id).find_annotation(annotation_name).json(with_context=True)
            except KeyError as e:
                raise AnnotationNotFound(annotation_name=annotation_name, manifest_id=manifest_id) from e

    @app.route('/manifests/<manifest_id>/manifest/search')
    def get_search(manifest_id: str):
        """Implements the search result annotation list response for a manifest.

        See also: https://iiif.io/api/search/1.0/#simple-lists"""
        with Timer(
            name=f'search for "{request.args["q"]}" in {manifest_id}',
            text='Time to {name}: {milliseconds:.3f} ms',
            logger=app.logger.info,
        ):
            ctx = app.config['papaya_context']
            manifest = ctx.get_manifest(manifest_id)
            try:
                results = SearchResultsList(manifest, request.args['q'])
            except KeyError as e:
                raise MissingQueryParameter(param_name=e.args[0]) from e

            return results.json(with_context=True)

    @app.route('/manifests/<manifest_id>/canvas/<canvas_name>/search')
    def get_annotation_list(manifest_id: str, canvas_name: str):
        """Implements the search result annotation list response for a canvas.

        See also: https://iiif.io/api/search/1.0/#simple-lists"""
        with Timer(
            name=f'search for "{request.args["q"]}" in canvas {canvas_name} in {manifest_id}',
            text='Time to {name}: {milliseconds:.3f} ms',
            logger=app.logger.info,
        ):
            ctx = app.config['papaya_context']
            try:
                canvas = ctx.get_manifest(manifest_id).find_canvas(canvas_name)
            except KeyError as e:
                raise CanvasNotFound(canvas_name=canvas_name, manifest_id=manifest_id) from e

            try:
                results = SearchResultsList(canvas, request.args['q'])
            except KeyError as e:
                raise MissingQueryParameter(param_name=e.args[0]) from e

            return results.json(with_context=True)

    app.register_error_handler(ProblemDetailError, problem_detail_response)

    return app
