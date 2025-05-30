import paho.mqtt.client as mqtt
import json
from app.config import Config

client = mqtt.Client()
client.connect(Config.MQTT_BROKER, Config.MQTT_PORT)
client.loop_start()

# metadata 전송
def publish_metadata(metadata_dict):
    metadata_json = json.dumps(metadata_dict)
    return client.publish("smartHome/metadata", metadata_json)
    