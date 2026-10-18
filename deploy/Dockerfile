# syntax=docker/dockerfile:1
# App-Image für ParlTopics (Dienste api und worker).
#
# Gebaut wird ausschliesslich aus deploy/airgap/wheels (make wheels) und dem fertigen Build der
# Web-App in web/dist (make web-build). Der Build braucht deshalb weder PyPI noch npm und lässt sich
# auch im Air-Gap neu bauen, wenn das Basis-Image geladen ist.
ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_INDEX=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY deploy/airgap/wheels/ /tmp/wheels/
RUN pip install --no-cache-dir --no-index --find-links=/tmp/wheels -r /tmp/wheels/requirements.txt \
 && pip install --no-cache-dir --no-index --no-deps /tmp/wheels/parltopics-*.whl \
 && rm -rf /tmp/wheels

COPY migrations/ migrations/
COPY prompts/ prompts/
COPY registry/ registry/
COPY web/dist/ web/dist/

RUN useradd --create-home --uid 10001 parltopics && chown -R parltopics /app/registry
USER parltopics

EXPOSE 8000
CMD ["uvicorn", "parltopics.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
