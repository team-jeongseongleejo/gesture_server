import os
import joblib
import requests
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestClassifier
from flask import Blueprint, jsonify
from firebase_admin import db
from datetime import datetime, timedelta
from astral import LocationInfo
from astral.sun import sun
import pytz

recommand_bp = Blueprint("recommand", __name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
MODEL_PATH = os.path.join(BASE_DIR, "models", "gesture_recommend_model.pkl")
ENCODER_PATH = os.path.join(BASE_DIR, "models", "encoder.pkl")

city = LocationInfo("Seoul", "KR", "Asia/Seoul", latitude=37.5665, longitude=126.9780)
timezone = pytz.timezone("Asia/Seoul")

mode_gestures = {
    "light": "one",
    "projector": "two",
    "curtain": "three",
    "fan": "four"
}

# 현재 기온 가져오기
def get_current_temperature():
    try:
        response = requests.get("https://api.openweathermap.org/data/2.5/weather", params={
            "q": "Seoul",
            "appid": "bde2733011591df872f6e37f11d51336",
            "units": "metric"
        })
        data = response.json()
        return float(data["main"]["temp"])
    except:
        return 24.0

@recommand_bp.route("/recommend_gesture_auto", methods=["GET"])
def recommend_gesture_auto():
    try:
        now = datetime.now(timezone)
        hour = now.hour
        weekday = now.weekday()
        temp = get_current_temperature()

        device_gesture = db.reference("user_info/current_device").get()
        current_device = db.reference(f"mode_gesture/{device_gesture}/label").get()
        if not current_device:
            return jsonify({"error": "현재 device 정보를 찾을 수 없습니다."}), 400

        s = sun(city.observer, date=now.date(), tzinfo=timezone)
        sunrise = s["sunrise"]
        sunset = s["sunset"]
        is_morning = sunrise <= now <= sunrise + timedelta(hours=1)
        is_evening = sunset - timedelta(minutes=30) <= now <= sunset + timedelta(hours=2)

        recommendations = []
        seen_pairs = set()

        def add_recommendation(device, gesture, reason):
            pair = (device, gesture)
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                recommendations.append({
                    "device": device,
                    "recommended_gesture": gesture,
                    "reason": reason
                })

        def add_device_sequence(target_device, gesture, reason):
            if (target_device, gesture) in seen_pairs:
                return
            if current_device != target_device:
                mode_gesture = mode_gestures.get(target_device)
                if mode_gesture and (target_device, mode_gesture) not in seen_pairs:
                    add_recommendation(target_device, mode_gesture, f"{target_device} 모드 진입을 추천해요!")
            add_recommendation(target_device, gesture, reason)

        status_refs = {
            dev: db.reference(f"status/{dev}").get() or {} for dev in mode_gestures
        }

        if temp > 27 and status_refs["fan"].get("power") != "on":
            add_device_sequence("fan", "small_heart", "현재 온도가 높음 (>27°C) 및 전원이 꺼짐")

        if is_morning and status_refs["curtain"].get("power") != "on":
            add_device_sequence("curtain", "small_heart", "아침 시간대 커튼 열기")

        if is_evening and status_refs["light"].get("power") != "on":
            add_device_sequence("light", "small_heart", "저녁 시간대 전등 켜기")

        if os.path.exists(MODEL_PATH) and os.path.exists(ENCODER_PATH):
            model = joblib.load(MODEL_PATH)
            encoder = joblib.load(ENCODER_PATH)

            for device in mode_gestures:
                status = status_refs[device]
                log = status.get("log", {})
                power = status.get("power", "unknown")
                fan_mode = log.get("fan_mode", "unknown")
                wind_power = log.get("wind_power", "unknown")
                color = log.get("color", "unknown")

                X_input = encoder.transform([[
                    hour, weekday, temp, device, power, fan_mode, wind_power, color
                ]]).toarray()

                pred = model.predict(X_input)[0]
                add_device_sequence(device, pred, "당신의 생활패턴에 딱 맞는 추천입니다.")

        if not recommendations:
            return jsonify({"message": "추천할 제스처가 없습니다."})

        return jsonify({
            "timestamp": now.isoformat(),
            "recommendations": recommendations[:6]  # 모드 포함 최대 3쌍 (6개)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def extract_features(log_entry):
    try:
        createdAt = log_entry["createdAt"]
        dt = datetime.fromisoformat(createdAt)
        hour = dt.hour
        weekday = dt.weekday()
        temp = float(log_entry.get("temperature", 24.0))
        return {
            "hour": hour,
            "weekday": weekday,
            "temperature": temp,
            "device": log_entry.get("device", "unknown"),
            "power": log_entry.get("power", "unknown"),
            "fan_mode": log_entry.get("fan_mode", "unknown"),
            "wind_power": log_entry.get("wind_power", "unknown"),
            "color": log_entry.get("color", "unknown"),
            "gesture": log_entry.get("gesture")
        }
    except:
        return None


def train_model():
    logs = db.reference("log_table").get() or {}
    dataset = []

    for entry in logs.values():
        features = extract_features(entry)
        if features and features.get("gesture"):
            dataset.append(features)

    if not dataset:
        print("\u274c 학습할 데이터가 없습니다.")
        return

    X_raw = [{k: v for k, v in d.items() if k != "gesture"} for d in dataset]
    y = [d["gesture"] for d in dataset]

    encoder = OneHotEncoder(handle_unknown="ignore")
    X_encoded = encoder.fit_transform([
        [
            d["hour"], d["weekday"], d["temperature"], d["device"],
            d["power"], d["fan_mode"], d["wind_power"], d["color"]
        ] for d in X_raw
    ]).toarray()

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_encoded, y)

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    joblib.dump(encoder, ENCODER_PATH)
    print("\u2705 모델 학습 및 저장 완료")
