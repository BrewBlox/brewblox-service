FROM python:3.7
EXPOSE 5000
WORKDIR /app

COPY ./dist /build/dist

RUN pip3 install wheel \
    && pip3 wheel /build/dist/* --wheel-dir=/wheeley \
    && pip3 install --no-index --find-links=/wheeley brewblox-service \
    && pip3 freeze

ENTRYPOINT ["python3", "-m", "brewblox_service"]
