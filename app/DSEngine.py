
from deepspeech import Model

from scipy.signal import resample_poly as resampler
import numpy as np

from time import sleep
from concurrent.futures import ThreadPoolExecutor
from base64 import b64decode
import os,asyncio,json
import webrtcvad

from websockets.exceptions import ConnectionClosed
from concurrent.futures import CancelledError

from timeit import default_timer
from functools import partial

from logging import getLogger
logger = getLogger('DSApp')

class DSEngine:

    @classmethod
    async def create(cls,websocket=None,**kwargs):

        self = DSEngine()
        modelPath = os.path.join(kwargs.get("DEEPSPEECH_ROOT_PATH"),kwargs.get("MODEL"))
        alphabetPath = os.path.join(kwargs.get("DEEPSPEECH_ROOT_PATH"),kwargs.get("ALPHABET"))
        logger.info('Loading model from file {}'.format(modelPath))#, file=sys.stderr)
        modeLoad_start = default_timer()

        self.model = Model(modelPath,
            int(kwargs.get("NFEATS",26)),
            int(kwargs.get("NCONTEXT",9)),
            alphabetPath,
            int(kwargs.get("BEAMWIDTH",500)))

        if kwargs.get("LM") is not None and kwargs.get("TRIE") is not None:
            lmPath = os.path.join(kwargs.get("DEEPSPEECH_ROOT_PATH"),kwargs.get("LM"))
            triePath = os.path.join(kwargs.get("DEEPSPEECH_ROOT_PATH"),kwargs.get("TRIE"))
            self.model.enableDecoderWithLM(alphabetPath,lmPath,triePath,float(kwargs.get("LMALPHA",0.75)),float(kwargs.get("LMBETA",1.85)))

        modeLoad_end = default_timer() - modeLoad_start
        logger.info('Loaded model in {:.3}s.'.format(modeLoad_end))#, file=sys.stderr)

        #each frames is like 20ms
        self.pre_alloc_frames = round(float(kwargs.get("PRE_ALLOC_TIME",2.0))/0.02)
        self.ctx = self.model.setupStream(pre_alloc_frames=self.pre_alloc_frames)
        self.tail =[]

        self.inputSr=int(kwargs.get("INPUT_SAMPLE_RATE",16000))
        self.targetSr=16000
        #resample stuff
        ## TODO: parametrize with gdc and test for different sample rates
        if self.inputSr > self.targetSr:
            self.up = self.inputSr//self.targetSr
            self.down = 1
        else:
            self.up = self.targetSr//self.inputSr
            self.down = 1
        self.prevResampledChunk=[]
        self.resampleOffset = -1
        self.currentTime = 0

        self.secsInQueue=0.0
        self.secsInStream=0.0

        self.websocket=websocket
        self.ws_id = websocket.client[1]

        self.lastValidTranscription=''

        self.dsAsyncLoop = asyncio.get_event_loop()

        self.msgQueue = asyncio.Queue()

        self.VAD = webrtcvad.Vad(1)
        self.noSpeechSecs = 0.0 #counts nospeech seconds
        self.speechSecs =0.0 #counts speech seconds
        self.minSpeechSecs = float(kwargs.get("MIN_SPEECH_SECS",0.05))
        self.minNoSpeechSecs = float(kwargs.get("MIN_NOSPEECH_SECS",0.05))

        self.decodeTriggerInterval=float(kwargs.get("DECODE_TRIGGER_INTERVAL",1.0))
        self.VADQueue=[]
        self.VADStartTrimIndx=-1
        self.VADEndTrim=0
        self.secsInVADqueue=0.0

        self.consume=True

        self.feed=False
        self.consumerTask = self.dsAsyncLoop.create_task(self.consumer())

        return self


    async def enqueue(self,data):
        await self.msgQueue.put(data)

    async def consumer(self):

        while self.consume:
            #logger.info("CONSUMING... %s",self.consume)
            msg = await self.msgQueue.get()
            await self.parseMessage(msg)
            self.msgQueue.task_done()

        return True

    async def parseMessage(self,msg):

        if self.websocket.client_state.name=="CONNECTED":
            '''
            A new audio buffer is coming.
            Steps:
            #1- save buffers in VADQueue
            #2- if this buffer is "speech", save its index (VADStartTrimIndx) inside
                the queue,including some no-speech buffers before if any
            #3- once the minimum speech seconds has been reached, take a sublist
                of buffers from the VADQueue starting from VADStartTrimIndx. The
                feed flag now is True
            #4- from now every buffer coming from the client will be directly
                sent to the DeepSpeech stream. Meanwhile a counter of speech/noSpeech
                seconds is updated
            #5- when noSpeechSecs is higher than minNoSpeechSecs, no more buffers
                will be feeded
            '''
            if msg["type"] == "AUDIO_BUFFER":

                samples = b64decode(msg["data"])
                numOfSamples = len(samples)/2

                isSpeech = self.VAD.is_speech(samples, self.inputSr)

                info= {
                    "chunkNum": msg.get("count",-1),
                    "isSpeech": isSpeech
                }
                logger.info("TIME {:.3}".format(msg["count"]*(numOfSamples/self.inputSr)))

                #1
                self.VADQueue.append(samples)
                self.secsInVADqueue+=numOfSamples/self.inputSr
                #2
                if isSpeech:
                    self.speechSecs += numOfSamples/self.inputSr #4
                    self.noSpeechSecs=0.0

                    if self.VADStartTrimIndx < 0:
                        ## TODO: parametrize this number using milli/seconds as reference!
                        ofs= min(10,len(self.VADQueue))
                        self.VADStartTrimIndx= len(self.VADQueue) - ofs #if (len(self.VADQueue) - ofs)>0 else len(self.VADQueue)

                else:
                    self.noSpeechSecs += numOfSamples/self.inputSr #4
                #3
                if self.speechSecs>=self.minSpeechSecs and not self.feed:
                    logger.info("self.VADStartTrimIndx: %s, queuelen %s",self.VADStartTrimIndx,len(self.VADQueue))
                    self.feed = True
                    buffers = self.VADQueue[self.VADStartTrimIndx:]

                    samples = b''.join(buffers)
                    logger.info("len(buffers): %s len(samples): %s",len(buffers),len(samples))
                #4
                if self.feed:

                    await self.feedAudio(samples,info)
                    if round(self.secsInStream,2) % self.decodeTriggerInterval == 0:
                        logger.info("DECODING")
                        await self.doStt()
                else:
                    logger.info("NOT FEEDED BUT QUEUED chunk {}".format(info.get("chunkNum"))+" isSpeech:{}".format(isSpeech)+" nospeechsecs:{:.3}s".format(self.noSpeechSecs)+" speechSecs:{:.3}s".format(self.speechSecs))

                #5
                if self.noSpeechSecs>self.minNoSpeechSecs and self.secsInStream>0:
                    logger.info("FINISH STREAM-noSpeechSecs %s speechSecs %s total %s",self.noSpeechSecs,self.speechSecs,self.secsInStream)
                    self.feed=False
                    startIndx = self.VADStartTrimIndx
                    self.VADStartTrimIndx=-1
                    self.VADQueue = []
                    self.noSpeechSecs=self.speechSecs=0.0

                    await self.doStt(finishStream=True)

            #flush the deepspeech stream with a last transcription
            elif msg["type"] == "REQ_TRANSCRIPTION":
                logger.info("REQ_TRANSCRIPTION")
                await self.doStt(finishStream=True)
            else:
                logger.warning("Message not recognized!")
                await asyncio.sleep(0.05)

        #return True #QUESTION:  useful for asyncio purpose?

    async def feedAudio(self,samples,info):

        feedFuture = self.dsAsyncLoop.run_in_executor(None,self._feedAudioContent,samples,info);
        #feedFuture.add_done_callback(self.callback)
        # TODO: Are exceptions handled in the right way?
        # CancelledError exception while feeding and the client disconnects
        try:
            await feedFuture#asyncio.gather(feedFuture)
        except CancelledError:
            #logger.exception("ERROR")
            logger.error("feedFuture done %s",feedFuture.done())
            logger.error("feedFuture cancelled %s",feedFuture.cancelled())
            #self.consume=False
        except:
            logger.exception("ERROR")
            raise



    def _feedAudioContent(self,data,msg):
        if len(data)<1:
            logger.warning("EMPTY DATA WHILE FEEDING!")

        feed_start = default_timer()

        if self.inputSr != self.targetSr:

            #resample the audio.
            # TODO: test more sampling rates. Rates working:
            #   8000khz -> 16000 khz
            audio = np.array(self.resample(data), dtype=np.int16)
        else:
            audio = np.frombuffer(data, dtype=np.int16)

        self.model.feedAudioContent(self.ctx,audio)


        numOfSamples = len(data)/2
        secs = numOfSamples/self.inputSr
        self.secsInStream += secs

        feed_end = default_timer() - feed_start
        logger.info('FEED done in: {:.3}s;'.format(feed_end)+
        ' isSpeech {};'.format(msg["isSpeech"])+
        ' seconds feeded {:.3}s;'.format(secs)+
        ' seconds total {:.3}s;'.format(self.secsInStream)+
        ' chunk number {}'.format(msg["chunkNum"])
        )
        # if msg.get("boundaries"):
        #     logger.info("Saving audio from chunk %s to %s",msg["boundaries"][0],msg["boundaries"][1])
        #     buffers = self.VADQueue[msg["boundaries"][0]:msg["boundaries"][1]]
        #     buffers.insert(0,bytes(4000))
        #     buffers.append(bytes(4000))
        #     b = b''.join(buffers)
        #     audio = np.frombuffer(b, dtype=np.int16)
        #     librosa.output.write_wav("./"+str(msg["boundaries"][0])+"-"+str(msg["boundaries"][1])+".wav",audio/0x8000,self.inputSr)

        return self.secsInStream


    async def doStt(self,finishStream=False):
        decodeFuture = self.dsAsyncLoop.run_in_executor(None,partial(self.decode,finishStream))
        try:
            result= await decodeFuture
            self.secsInStream = 0;
            await self.sendResult(result)
        except CancelledError:
            logger.exception("DOSTT CANCELLEDERROR")
        except:
            logger.exception("Unknown error")
            raise

    def decode(self,finishStream=False):

        #self.busy=True
        decode_start = default_timer()
        if finishStream:

            result=self.model.finishStreamWithMetadata(self.ctx)

            setup_start = default_timer()
            self.ctx = self.model.setupStream(pre_alloc_frames=self.pre_alloc_frames)
            setup_end = default_timer() - setup_start
            logger.info('Setup done in: {:.3}s.'.format(setup_end))
        else:
            result=self.model.intermediateDecode(self.ctx)
        decode_end = default_timer() - decode_start
        logger.info('Decode done in: {:.3}s.'.format(decode_end))

        return result

    async def sendResult(self,result):

        if type(result) == str:
            data = {"transcription":result,"metadata":{}}
        else: #metadata
            transcription = ''.join(item.character for item in result.items)
            data ={
            "transcription": transcription,
            "metadata":{
                    "numItems": result.num_items,
                    "probability": result.probability,
                    "indx2charMetadata":json.dumps({i:{"char":el.character,"start_time":el.start_time,"timestep":el.timestep} for i,el in enumerate(result.items)})
                }
            }
        logger.info("CONNECTED? %s",self.websocket.client_state.name)
        if self.websocket.client_state.name=="CONNECTED":

            structuredResult = {
                "type": "TRANSCRIPTION",
                "clientId": self.ws_id,
                "data": data
            }
            logger.info("RESULT %s",structuredResult)
            try:
                await self.websocket.send_json(structuredResult)
            except ConnectionClosed as exc:
                #await websocket.close(code=1000)
                logger.error("ConnectionClosed %s",exc)
            except:
                raise


    async def clear(self):
        logger.info("CLEARING")
        await self.msgQueue.join()
        self.consumerTask.cancel()
        try:
            res = await self.consumerTask

            logger.info("results %s",res)
        except asyncio.CancelledError:
            logger.info("asyncio.CancelledError")
        finally:
            logger.info("Feeder done? %s",self.consumerTask.done())
            logger.info("Feeder cancelled? %s",self.consumerTask.cancelled())
            logger.info("Audio queue size: %s",self.msgQueue.qsize())
            self.consume=False


    def resample(self,data):
        #len data: N

        nZeros= 10 # TODO: parametrize nZeros
        data16 = np.frombuffer(data,dtype=np.int16) #len data16: N/2
        pad = np.zeros(nZeros,dtype=np.int16) #len: p
        data16 = np.concatenate((pad,data16,pad)) #len: N/2+2*p
        resampled = resampler(data16,self.up,self.down) #len: (N/2)*(up/down)

        # if no samples saved from previous iteration
        if len(self.prevResampledChunk)==0:
            # save half of the current resampled buffer
            self.prevResampledChunk = resampled[len(resampled)//2:]
            # the actual buffer is just the first half
            buffer = resampled[0:len(resampled)//2]
        else:
            #crossfade between the previous chunk and the new resampled buffer
            #to prevent audio distortion

            #total overlap of buffer's tails: nZeros*4 offset
            buffer = np.zeros(len(self.prevResampledChunk)+len(resampled)-(nZeros*4))
            #fill the first half of the final buffer with the previous saved chunk
            buffer[0:len(self.prevResampledChunk)] = self.prevResampledChunk
            #copy the resampled samples in a way that the sum of the smoothed boundaries
            #given by the resample process will not create discontinuities over the signal
            buffer[(len(self.prevResampledChunk)-(nZeros*4)):]+=resampled
            buffLen = len(data) # TODO: len(data) = (N/2)*(up/down) ?
            #save the new chunk
            self.prevResampledChunk = buffer[buffLen:]
            #the final buffer to return
            buffer = buffer[0:buffLen]


        return buffer

    def callback(self,future):
        exc = future.exception()
        if exc:

            logger.exception("ERROR")
