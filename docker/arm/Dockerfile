FROM brewblox/rpi-python:3.7
EXPOSE 5000
WORKDIR /app

ARG service_info=UNKNOWN
ENV SERVICE_INFO=${service_info}

COPY ./dist /build/dist
COPY ./requirements.txt /build/requirements.txt

RUN pip3 install wheel \
    && pip3 wheel --wheel-dir=/wheeley-base -r /build/requirements.txt \
    && pip3 wheel --wheel-dir=/wheeley-base --find-links=/wheeley-base --no-index /build/dist/* \
    && pip3 install --find-links=/wheeley-base --no-index  brewblox-service \
    && pip3 freeze

ENTRYPOINT ["python3", "-m", "brewblox_service"]
