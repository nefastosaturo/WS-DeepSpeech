package wsclient;


import java.net.URI;
import java.util.Date;

import org.java_websocket.client.WebSocketClient;
import org.java_websocket.handshake.ServerHandshake;
import org.json.JSONObject;

public class WSClient extends WebSocketClient {
	private long timeDrift;
	private boolean setTimeDrift;
	private long time;
	private long timeCursor;
	private boolean isReady;
	public WSClient(URI serverUri) {
		
		super(serverUri);
		this.isReady=false;
		setTimeDrift=true;
		// TODO Auto-generated constructor stub
	}
	
	public void setReady(boolean value) {
		this.isReady=value;
	}
	public boolean isReady() {
		return this.isReady;
	}

	@Override
	public void onClose(int arg0, String arg1, boolean arg2) {
		// TODO Auto-generated method stub
		System.out.println("onclose "+arg0+","+arg1+","+arg2);
		System.out.println("time at open "+this.time);
		System.out.println("time at close "+System.currentTimeMillis());
		System.out.println("OPEN? "+this.isOpen());
	}

	@Override
	public void onError(Exception arg0) {
		// TODO Auto-generated method stub
		arg0.printStackTrace();
		System.out.println("ONERROR "+arg0.getMessage());
//		this.close();
	}

	@Override
	public void onMessage(String arg0) {
		
		JSONObject message = new JSONObject(arg0);
		String type = (String) message.get("type");
		JSONObject data =  (JSONObject) message.get("data");
		switch(type) {
		case "STATUS":
			System.out.println(data.getString("message"));
			this.isReady = data.getBoolean("result");
//			this.close();
			break;
		case "SETUP":

			this.time= System.currentTimeMillis();
			this.timeCursor=this.time;
			System.out.println(data.getString("message"));
			break;
			case "WELCOME_MSG":
				System.out.println("welcome message");
				if(setTimeDrift) {
					long serverTimeStamp = data.getLong("timestamp");
					long localTimestamp = new Date().getTime();
					timeDrift = localTimestamp - serverTimeStamp ;
					System.out.println("Time drif set. Delay of: "+timeDrift+"ms");
					setTimeDrift=false;					
				}
				break;
			case "RESULT":
				float probOfVoice = data.getFloat("voice");
				float probOfClassical = data.getFloat("classical");
				float probOfHit = data.getFloat("hit");
				float secondsProcessed = data.getFloat("secondsProcessed");
				System.out.println("voice "+probOfVoice+" classical "+probOfClassical+" hit "+probOfHit+" secondsProcessed "+secondsProcessed);

				break;
			case "TRANSCRIPTION":				
				String transcription =  data.getString("transcription");
				String id =  message.get("clientId").toString();
				
				this.timeCursor= System.currentTimeMillis();
				Date date = new Date();
				StringBuilder stringBuilder = new StringBuilder();
				stringBuilder.append(id);
				stringBuilder.append(" ");
				stringBuilder.append((this.timeCursor-this.time));
				stringBuilder.append(" ");
				stringBuilder.append(date.getHours());
				stringBuilder.append(":");
				stringBuilder.append(date.getMinutes());
				stringBuilder.append(":");
				stringBuilder.append(date.getSeconds());
				stringBuilder.append(" ");
				stringBuilder.append(transcription);
				System.out.println(stringBuilder.toString());
				JSONObject metadata = data.getJSONObject("metadata");
				if (!metadata.isEmpty()){
					int numItems = metadata.getInt("numItems");
					float prob = metadata.getFloat("probability");
					String indx2charMetadata = (metadata.get("indx2charMetadata")).toString();
					stringBuilder = new StringBuilder();
					stringBuilder.append(numItems);
					stringBuilder.append(" ");
					stringBuilder.append(prob);
					stringBuilder.append(" ");
					stringBuilder.append(indx2charMetadata);
					System.out.println(stringBuilder.toString());
					
				}
				
				break;
			default:
				// TODO Auto-generated method stub
				System.out.println("onmessage "+arg0);
		}
	}

	@Override
	public void onOpen(ServerHandshake arg0) {
		// TODO Auto-generated method stub
		System.out.println("onopen "+arg0);
		this.time= System.currentTimeMillis();
		this.timeCursor=this.time;
		
	}
	
}