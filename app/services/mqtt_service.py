import paho.mqtt.client as mqtt
import json
from app.config import Config

client = mqtt.Client()
client.connect(Config.MQTT_BROKER, Config.MQTT_PORT)
client.loop_start()

def publish_ir(payload):
    return client.publish(Config.MQTT_TOPIC, json.dumps(payload))