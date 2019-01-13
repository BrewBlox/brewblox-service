FROM brewblox/rpi-python:3.7
EXPOSE 5000
WORKDIR /app

COPY ./dist /build/dist
COPY ./requirements.txt /build/requirements.txt

RUN pip3 install wheel \
    && pip3 wheel --wheel-dir=/wheeley -r /build/requirements.txt \
    && pip3 wheel --wheel-dir=/wheeley --find-links=/wheeley --no-index /build/dist/* \
    && pip3 install --find-links=/wheeley --no-index  brewblox-service \
    && pip3 freeze

ENTRYPOINT ["python3", "-m", "brewblox_service"]
