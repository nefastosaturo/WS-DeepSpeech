
from multiprocessing import cpu_count
from starlette.config import Config
import urllib.request,tarfile
import os
import logging
import threading,time

appConfig = Config("./app/appConfig")

chdir = "app/"


bind = "0.0.0.0:5000"
workers = cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornH11Worker"
timeout = 60
loglevel = "warning"
preload = True
preload_app = True

model_filenames =["alphabet.txt","trie","lm.binary","output_graph.pbmm"]


logger = logging.getLogger('DSApp')
formatter = logging.Formatter('[%(process)d] [%(asctime)s] [%(name)s] [%(levelname)s] [%(message)s]',"%Y-%m-%d %H:%M:%S")
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)


def setVerbosity(level=30):

    if level==logging.DEBUG:

        ch.setLevel(level)

        wsLogger = logging.getLogger('websockets')
        wsLogger.setLevel(level)
        wsLogger.addHandler(ch)

        asyncioLogger = logging.getLogger('asyncio')
        asyncioLogger.setLevel(level)
        asyncioLogger.addHandler(ch)

        from asyncio import get_event_loop
        get_event_loop().set_debug(True)

    else:
        logger.setLevel(level)
        ch.setLevel(level)
        logger.addHandler(ch)

if appConfig('DEBUG', cast=bool):
    setVerbosity(logging.DEBUG)
elif appConfig('VERBOSE', cast=bool):
    setVerbosity(logging.INFO)
else:
    setVerbosity()


def when_ready(server):
    def thread_function(dsPath):
        #import os

        if not os.path.isdir(dsPath):
            logger.warning("Downloading deepspeech data...")

            os.mkdir(dsPath)
            lockfile = open("lockfile","w")
            lockfile.close()
            dsVersion = appConfig("DEEPSPEECH_VERSION",cast=str)
            dsModelTarUrl = "https://github.com/mozilla/DeepSpeech/releases/download/v"+dsVersion+"/deepspeech-"+dsVersion+"-models.tar.gz"
            stream = urllib.request.urlopen(dsModelTarUrl)
            with tarfile.open(fileobj=stream, mode="r|gz") as dsModelTar:

                
                #print("NEL WITH: GETCWD",os.getcwd(),"OSDIRNAME",os.path.dirname(os.path.abspath(__file__)))
                dsModelTar.extractall(path=dsPath) # extract
                currPath = os.path.join(dsPath,"deepspeech-"+dsVersion+"-models")
                for filename in os.listdir(currPath):
                    if filename in model_filenames:
                        os.rename(os.path.join(currPath,filename), os.path.join(dsPath,filename))
                    else:
                        os.remove(os.path.join(currPath,filename))

            os.remove("lockfile")
            logger.warning("Done!")

        logger.warning("DeepSpeech data ready!")


    x = threading.Thread(target=thread_function, args=(appConfig('DEEPSPEECH_ROOT_PATH',cast=str),))
    x.start()
