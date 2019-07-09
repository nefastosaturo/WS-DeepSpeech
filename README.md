# DeepSpeech over Websocket

A [DeepSpeech](https://github.com/mozilla/DeepSpeech) webserver with resampling capabilities that run over websockets through [Starlette](https://github.com/encode/starlette).


## Requirements

* `Python 3.6+`
* [`Starlette 0.12`](https://github.com/encode/starlette)
* [`Uvicorn 0.7`](https://github.com/encode/uvicorn)
* [`Gunicorn 19.9`](https://github.com/benoitc/gunicorn)
* [`Scipy 1.3`](https://www.scipy.org/)
* [`Webrtcvad 2.0`](https://github.com/wiseman/py-webrtcvad)


## Installation

I'm using miniconda so:
```shell
$ conda create --name wsDSpeech python=3.6 # or 3.7
$ conda activate wsDSpeech
$ pip install -r requirements.txt
```

## Run
First, set up the correct `INPUT_SAMPLE_RATE` in `appConfig` according to the audio file that will be streamed to the server.

Then, if you want to use the Dockerfile just run:

```shell
$ docker build -t deepspeech .
$ docker run -t deepspeech
```
or locally:

```shell
$ cp appConfig app/appConfig
$ gunicorn -c guConfig.py app:app
```

in the example folder there is a simple Java client.
* Choose how many connections:
	```java
	nrClient=2
	```

* Put the correct ip address:
	```java
	WSClient c=new WSClient(new URI("ws://127.0.0.1:5000/ws"));
	```
* Run it

## Settings
`appConfig` contains all the settings used.

On first run, DeepSpeech models will be downloaded under the `DEEPSPEECH_ROOT_PATH`.

If you want more verbosity, flag `VERBOSE`/`DEBUG` to `True`

`guConfig` contains all the settings related to GUnicorn, including the deepspeech model downloading part.


## TODOs
* Python client example
* Manage memory leaking (avoid to force workers restart)
* Handle async/future exceptions
* Use a lighter docker as base image (Alpine?)
