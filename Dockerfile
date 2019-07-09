FROM ubuntu:18.04

ENV 	BUILD_PACKAGES="\
		build-essential \
		python3-distutils \
		curl \
		python3.7-dev" \
	APT_PACKAGES=" \
		ca-certificates \
		python3.7-minimal"

RUN set -ex; \
	apt-get update -y; \
	apt-get upgrade -y; \
	apt-get install -y --no-install-recommends ${APT_PACKAGES}; \
	apt-get install -y --no-install-recommends ${BUILD_PACKAGES};

# make some useful symlinks that are expected to exist
RUN cd /usr/bin \
	&& ln -s idle3.7 idle \
	&& ln -s pydoc3.7 pydoc \
	&& ln -s python3.7 python \
	&& ln -s python3.7-config python-config

COPY requirements.txt .

# python packages installation step
RUN set -ex; \
	curl -fSsL -O https://bootstrap.pypa.io/get-pip.py && \
	    python get-pip.py && \
	    rm get-pip.py; \
	#     pip install -U -v setuptools wheel; \
	pip install -U -v -r requirements.txt;

# clean/uninstall some stuff also pip
RUN set -ex; \
	python -m pip uninstall -y pip; \
	apt-get remove --purge --auto-remove -y ${BUILD_PACKAGES}; \
	apt-get clean; \
	apt-get autoclean; \
	apt-get autoremove; \
	rm -rf /tmp/* /var/tmp/*; \
	rm -rf /var/lib/apt/lists/*; \
	rm -rf /var/cache/apt/archives/*.deb \
	/var/cache/apt/archives/partial/*.deb \
	/var/cache/apt/*.bin; \
	find /usr/lib/python3 -name __pycache__ | xargs rm -rf; \
	rm -rf /root/.[acpw]*; \
	rm -rf $LIB_FOLDER;


#copy needed files
COPY app ./app
COPY appConfig ./app/
COPY guConfig.py .

ENV LC_ALL "C.UTF-8"
ENV LANG "C.UTF-8"

#main script to run
ENTRYPOINT ["gunicorn","-c","guConfig.py","app:app"]
#WORKDIR /app
#ENTRYPOINT ["uvicorn","--workers","17","--host","0.0.0.0","--port","5000","--http","h11","--log-level","warning","app:deepspeech_server"]
