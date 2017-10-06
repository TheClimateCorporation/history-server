FROM python:2.7.11

RUN apt-get update && apt-get install -y sudo

RUN mkdir -p /usr/src/app
RUN mkdir -p /usr/src/app/static
RUN mkdir -p /usr/src/app/templates

WORKDIR /usr/src/app

# only copy what is exactly needed, NO MORE.

COPY src/requirements.txt /usr/src/app/
# do this as fast as possible, to minimize build time.
RUN pip install --no-cache-dir -r requirements.txt

COPY src/run_twistd.sh /usr/src/app/run_twistd.sh
COPY src/web.py /usr/src/app/web.py
COPY src/backend.py /usr/src/app/backend.py

COPY src/static/ /usr/src/app/static/

COPY src/templates/ /usr/src/app/templates/

COPY docs/DESIGN.md /usr/src/app/static/DESIGN.txt

COPY git_hash /usr/src/app/git_hash
COPY build_date /usr/src/app/build_date
COPY env.properties.toml /usr/src/app/env.properties.toml


EXPOSE 5000
EXPOSE 5001

CMD ./run_twistd.sh
