FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ffmpeg (and the ffprobe that ships with it) for reading a video's real
# duration and sampling still frames out of it. Videos have no EXIF and no
# thumbnail, so without this there is nothing for the vision step to look at
# and every video lands in the pool as a placeholder.
# openscad: AURON's 3D parts (app/cad) -- headless, the STL export needs no display.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg openscad \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system jarvis && adduser --system --ingroup jarvis jarvis

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
# licence-plate detector (app/instagram_content/plates.py): fetched once here, checksum pinned --
# never at runtime, and no picture ever leaves the machine
RUN mkdir -p /opt/models && python -c "import urllib.request,hashlib; \
d=urllib.request.urlopen('https://github.com/ankandrew/open-image-models/releases/download/assets/yolo-v9-t-640-license-plates-end2end.onnx').read(); \
assert hashlib.sha256(d).hexdigest()=='c3c1026ca7d0585dd88084d68182dd897113712fa734ae1557ca70174440c076', 'plate model checksum'; \
open('/opt/models/plates-yolo-v9-t-640.onnx','wb').write(d)"

COPY app ./app

RUN mkdir -p /data /logs && chown -R jarvis:jarvis /app /data /logs
USER jarvis

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
