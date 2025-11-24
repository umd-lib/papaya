FROM python:3.14.0

EXPOSE 5000

WORKDIR /opt/papaya

COPY src pyproject.toml /opt/papaya/

RUN pip install .

ENTRYPOINT [ "papaya" ]
