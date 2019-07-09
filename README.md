# DeepSpeech over Websocket

A DeepSpeech webserver with resampling capabilities that run over websockets through Starlette.


## Requirements

* `Python 3.6+`
* `Starlette 0.12`
* `Uvicorn 0.7`
* `Gunicorn 19.9`
* `Scipy 1.3`
* `Webrtcvad 2.0`


## Installation

I'm using miniconda so:
```shell
$ conda create --name wsDSpeech python=3.6 # or 3.7
$ conda activate wsDSpeech
$ pip install -r requirements.txt
```

## Run

if you want to use the Dockerfile just run:

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



## TODOs
* Python client example
* Manage memory leaking (avoid to force workers restart)
* Handle async/future exceptions
* Use a lighter docker as base image (Alpine?)
