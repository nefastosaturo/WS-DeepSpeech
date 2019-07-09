package wsclient;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocketFactory;
import javax.sound.sampled.AudioInputStream;
import javax.sound.sampled.AudioSystem;
import javax.sound.sampled.UnsupportedAudioFileException;

import java.io.File;
import java.io.IOException;
import java.util.Base64;
import java.util.ArrayList;
import java.net.URI;
import java.net.URISyntaxException;



import org.json.JSONObject;
public class Main {

	public static void main(String[] args) throws UnsupportedAudioFileException, IOException, InterruptedException, URISyntaxException {
		System.setProperty(org.slf4j.impl.SimpleLogger.DEFAULT_LOG_LEVEL_KEY, "INFO");

		File fileIn = new File("../8khz_01.wav"); 

		AudioInputStream audioInputStream = AudioSystem.getAudioInputStream(fileIn);
		
		float secsForFrame = 0.02f;
		int samplerate = 8000;
		int numBytes = (int) ((secsForFrame*samplerate)*2); //* bytesPerFrame; 

		int msWait =(int) (((numBytes/2)/ (float) samplerate)*1000);

		byte[] audioBytes = new byte[numBytes];
		ArrayList<WSClient> clients = new ArrayList<WSClient>();
		
		/*SSL STUFF*/
//		SSLContext sslContext = null;
//		SSLSocketFactory factory = null;
//		try {
//
//			//if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP)
//			sslContext = SSLContext.getInstance( "TLSv1.2" );
//			//else	
//			//   sslContext = SSLContext.getInstance( "TLS" );
//			sslContext.init( null, null, null ); // will use java's default key and trust store which is sufficient unless you deal with self-signed certificates
//			factory = sslContext.getSocketFactory();// (SSLSocketFactory) SSLSocketFactory.getDefault();
//
//		} catch (Exception ex) {
//			ex.printStackTrace();
//		}
//		and then add "wss" to uri

		boolean allReady = false;
		for(int i=0; i<6; i++){
			WSClient c=new WSClient(new URI("ws://127.0.0.1:5000/ws"));
			clients.add(c);

			c.connectBlocking();
			c.setConnectionLostTimeout( 0 );
		}
		while(!allReady) {
			

			for(WSClient c : clients) {
				JSONObject json = new JSONObject();						      
				json.put("type","STATUS");
				c.send(json.toString());
				allReady= true && c.isReady();

			}

			System.out.println("all ready? "+allReady);


			Thread.sleep(2000);	
		}
		for(WSClient c : clients) {
			JSONObject json = new JSONObject();						      
			json.put("type","SETUP");
			c.send(json.toString());

		}
		
		//test purpose
		int breakAfter = 50000;
		int c=0;

		int numBytesRead = 0;
		
		while ((numBytesRead =audioInputStream.read(audioBytes)) != -1) {

			//test purpose
			if(c>=breakAfter) {
				break;
			}
			
			Thread.sleep(msWait);

			// Here, do something useful with the audio data that's 
			// now in the audioBytes array...
			String b64 = new String(Base64.getEncoder().encode(audioBytes));
			JSONObject json = new JSONObject();						      
			json.put("type","AUDIO_BUFFER");
			json.put("count", c);
			json.put("data",b64);

			for (WSClient client: clients) {

				if (!client.isClosed()){
					client.send(json.toString());
				}

			}
			c++;

		}

		JSONObject j= new JSONObject();
		j.put("type","REQ_TRANSCRIPTION");
		j.put("data","");
		for (WSClient client: clients) {

			if (!client.isClosed()){
				client.send(j.toString());
			}						      

			System.out.println("REQ");
		}
		System.out.println("DONE");

	}
}	

