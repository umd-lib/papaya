# papaya

IIIF Presentation API Application

## Configuration

### Environment Variables

* **`PAPAYA_FCREPO_ENDPOINT`** URL of the Fedora repository. This is not 
  directly accessed, but is used when translating between URIs and IIIF 
  identifiers.
* **`PAPAYA_FCREPO_PREFIX`** Prefix string to use in IIIF identifiers for 
  resources in the Fedora repository.
* **`PAPAYA_SOLR_ENDPOINT`** URL of the Solr server that will provide the 
  metadata about the resources.
* **`PAPAYA_IIIF_IMAGE_ENDPOINT`** URL of the IIIF Image API server that 
  provides additional metadata about the images.
* **`PAPAYA_THUMBNAIL_WIDTH`** Maximum width of thumbnail images included 
  in the manifest.
* **`PAPAYA_LOGO_URL`** URL of an image file to be used as the logo in the 
  manifest.
* **`PAPAYA_METADATA_QUERIES_FILE`** YAML or JSON formatted file that 
  contains a mapping from metadata field label to a [jq query] to retrieve 
  the value or values for that field from the Solr document for a resource.

### Files

* **`METADATA_QUERIES_FILE`** YAML or JSON file that maps metadata field 
  labels to `jq` queries. For example:

    ```yaml
    Title: .object__title__display[]?
    Date: .object__date__edtf
    Bibliographic Citation: .object__bibliographic_citation__display[]?
    Creator: .object__creator[]?.agent__label__display[]
    Contributor: .object__contributor[]?.agent__label__display[]?
    Subject: .object__subject[]?.subject__label__display[]
    ```

## Development Setup

Requires Python 3.14

These setup instructions also assume that you are running the development 
stacks for both [umd-fcrepo] and [umd-iiif].

```zsh
git clone git@github.com:umd-lib/papaya.git
cd papaya
python -m venv --prompt "papaya-py$(cat .python-version)" .venv
source .venv/bin/activate
```

```zsh
pip install -e . --group test
```

Create a `.env` file with the following contents:

```dotenv
FLASK_DEBUG=1
PAPAYA_FCREPO_ENDPOINT=http://fcrepo-local:8080/fcrepo/rest
PAPAYA_FCREPO_PREFIX=fcrepo:
PAPAYA_SOLR_ENDPOINT=http://localhost:8985/solr/fcrepo
PAPAYA_IIIF_IMAGE_ENDPOINT=http://localhost:8182/iiif/2
PAPAYA_THUMBNAIL_WIDTH=250
PAPAYA_LOGO_URL=https://www.lib.umd.edu/images/wrapper/liblogo.png
PAPAYA_METADATA_QUERIES_FILE=metadata_queries.yml
```

### Running

```zsh
flask --app papaya.web run
```

The application will be available at <http://localhost:5000>

To listen on a different port, supply the `--port` option:

```zsh
flask --app papaya.web run --port 3001
```

### Tests

```zsh
pytest
```

With coverage information:

```zsh
pytest --cov src --cov-report term-missing tests
```

### Docker Image

Build the image:

```zsh
docker build -t docker.lib.umd.edu/papaya .
```

When running in a Docker container, the `PAPAYA_SOLR_ENDPOINT` and
`PAPAYA_IIIF_IMAGE_ENDPOINT` environment variables will need to be
adjusted to refer to the correct hostname.

Copy the `.env` file set up earlier to `docker.env`, and make these
changes:

```dotenv
PAPAYA_SOLR_ENDPOINT=http://host.docker.internal:8985/solr/fcrepo
PAPAYA_IIIF_IMAGE_ENDPOINT=http://host.docker.internal:8182/iiif/2
```

Run, using this new `docker.env` file:

```zsh
docker run --rm -it -p 3001:5000 --env-file docker.env docker.lib.umd.edu/papaya
```

## Name

This application is so-named because the phrase "Presentation API 
Application" could be abbreviated "PAPIA", which could be pronounced the 
same as "papaya", and because it is paired with the [Cantaloupe] IIIF 
image server in the UMD Libraries' IIIF services stack.

## License

Apache-2.0

See the [LICENSE](LICENSE) file for license rights and limitations.

[jq query]: https://jqlang.org/manual/
[umd-fcrepo]: https://github.com/umd-lib/umd-fcrepo
[umd-iiif]: https://github.com/umd-lib/umd-iiif
[Cantaloupe]: https://cantaloupe-project.github.io/
