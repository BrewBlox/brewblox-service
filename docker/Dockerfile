ARG python_version=3.8
ARG service_info=UNKNOWN

FROM python:${python_version}
EXPOSE 5000
WORKDIR /app

ENV SERVICE_INFO=${service_info}

COPY ./dist /build/dist

RUN pip3 install wheel \
    && \
    pip3 wheel \
    --wheel-dir=/wheeley-base \
    /build/dist/* \
    && \
    pip3 install \
    --find-links=/wheeley-base \
    --no-index \
    brewblox-service \
    && \
    pip3 freeze

ENTRYPOINT ["python3", "-m", "brewblox_service"]
