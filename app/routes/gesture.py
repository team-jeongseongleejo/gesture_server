from flask import Blueprint, request, jsonify
from firebase_admin import db
from app.routes.status import set_device_status
from app.services.mqtt_service import publish_ir
from flasgger.utils import swag_from
from datetime import datetime
import os

gesture_bp = Blueprint("gesture", __name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

def infer_device_status(device, control):
    cyclic_logs = {
        "light": {
            "color": ["전구색(Warm)", "주광색(Cool)", "주백색(Natural)"]
        },
        "projector": {
            "mute": ["무음 설정", "무음 해제"]
            #"HDMI_InOut" : ["HDMI in", "HDMI out"]
        },
        "fan": {
            "fan_mode": ["normal", "natural", "sleep", "eco"]
        }
    }

    static_logs = {
        "light": {
            "10min": "타이머 10분 설정",
            "2min": "타이머 2분 설정", 
            "30min": "타이머 30분 설정",
            "60min": "타이머 60분 설정",
            "brighter": "밝게",
            "dimmer": "어둡게"
        },
        "projector": {
            "HDMI_InOut": "HDMI in/out", 
            "HDMI_VOL_down": "HDMI 음량-",
            "HDMI_VOL_up": "HDMI 음량+",
            "VOL_down": "음량-",
            "VOL_up": "음량+",
            "down": "아래로",
            "home": "홈",
            "left": "왼쪽으로",
            "menu": "메뉴",
            "mid": "선택",
            "pointer": "포인터",
            "right": "오른쪽으로",
            "up": "위로"
        },
        "fan": {
            "horizontal" : "수평방향 전환",
            "stronger" : "바람 강하게",
            "vertical" : "수직방향 전환",
            "weaker" : "바람 약하게",
            "timer" : "타이머 설정"
        }
    }

    # 현재 상태 가져오기
    current_power = db.reference(f"status/{device}/power").get() or "off"
    log_data = db.reference(f"status/{device}/log").get()
    current_log = log_data if isinstance(log_data, dict) else {}

    # power 설정
    if control == "power":
        power = "off" if current_power == "on" else "on"
        log = {"power": power}
        if device == "fan" and power == "off":
            log["timer"] = "0"
        return power, log
    
    # cyclic log 설정
    cyclic = cyclic_logs.get(device, {}).get(control)
    if cyclic:
        prev = current_log.get(control)
        if prev in cyclic:
            idx = (cyclic.index(prev) + 1) % len(cyclic)
        else:
            idx = 0
        return current_power, {control: cyclic[idx]}

    # static log 설정
    static = static_logs.get(device, {}).get(control)
    if static:
        return current_power, {control: static}

def update_light_log(control, partial_log, log_ref):
    if control != "color":
        current_log = log_ref.get() or {}
        color = current_log.get("color")
        if color:
            partial_log["color"] = color

    return partial_log

def update_fan_log(control, partial_log, log_ref):
    current_log = log_ref.get() or {}
    fan_mode = current_log.get("fan_mode")
    wind_power = current_log.get("wind_power")
    timer = current_log.get("timer")

    if wind_power:
        partial_log["wind_power"] = wind_power
    if timer:
        partial_log["timer"] = timer

    if control == "fan_mode":
        if partial_log.get("fan_mode") == "eco" and wind_power:
            partial_log["wind_power"] = "2"
        else:
            pass
    elif control in ["stronger", "weaker"]:
        if fan_mode == "eco":
            partial_log["wind_power"] = "2"
        elif wind_power:
            wp = int(wind_power)
            wp = wp + 1 if control == "stronger" and wp < 12 else wp
            wp = wp - 1 if control == "weaker" and wp > 1 else wp
            partial_log["wind_power"] = str(wp)

        if fan_mode:
            partial_log["fan_mode"] = fan_mode
    elif control == "timer":
        if timer:
            t = float(timer)
            t = t + 0.5 if t < 7.5 else 0.0
        partial_log["timer"] = str(t)

        if fan_mode:
            partial_log["fan_mode"] = fan_mode
    else:      
        if fan_mode:
            partial_log["fan_mode"] = fan_mode
        if partial_log.get("power") == "off":
            partial_log["timer"] = "0.0"
    
    return partial_log


# 현재 모드에서 제스처 실행
@gesture_bp.route("/gesture", methods=["POST"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/gesture/gesture_post_handle_gesture.yml"))
def handle_gesture():
    gesture = request.get_json().get("gesture")
    if not gesture:
        return jsonify({"error": "제스처 값이 없습니다."}), 400
    
    # 인식된 손동작 업데이트
    db.reference(f"user_info/last_gesture").set(gesture)

    mode_data = db.reference(f"mode_gesture/{gesture}").get()
    selected_mode = mode_data.get("mode") if mode_data else None
    user_ref = db.reference(f"user_info/current_device")
    current_mode = user_ref.get()

    # 모드 설정
    if selected_mode:
        # 모드 선택
        if not current_mode or current_mode == "null":
            user_ref.set(gesture)
            return jsonify({"message": f"모드 '{selected_mode}'로 설정되었습니다."})
        # 모드 해제
        elif current_mode == gesture:
            user_ref.set("null")
            return jsonify({"message": f"모드 '{selected_mode}'가 해제되었습니다."})
        # 모드 전환
        else:
            user_ref.set(gesture)
            return jsonify({"message": f"모드 '{current_mode}'->'{selected_mode}'로 전환되었습니다."})

    if not current_mode or current_mode == "null":
        return jsonify({"error": "현재 모드가 설정되어 있지 않습니다."}), 400

    mode = db.reference(f"mode_gesture/{current_mode}/mode").get()
    control_data = db.reference(f"control_gesture/{mode}/{gesture}").get()
    if control_data is None:
        return jsonify({"error": f"모드 '{mode}'에 제스처 '{gesture}'가 없습니다."}), 404
    
    control = control_data.get("control")
    ir_data = db.reference(f"ir_codes/{mode}/{control}").get()
    if not ir_data or not ir_data.get("code"):
        return jsonify({"error": "IR 코드가 없습니다."}), 404
    
    payload = {
        "gesture" : gesture,
        "mode" : mode,
        "control" : control,
        "code" : ir_data["code"]
    }

    result = publish_ir(payload)
    if result.rc != 0:
        return jsonify({"error" : f"MQTT 전송 실패 (코드 {result.rc})"}), 500
    
    device = mode
    power, partial_log = infer_device_status(device, control)
    print(partial_log)

    log_ref = db.reference(f"status/{device}/log")
    # log 고정 변수 설정
    if device == "light":
        partial_log = update_light_log(control, partial_log, log_ref)
    elif device == "fan":
        partial_log = update_fan_log(control, partial_log, log_ref)

    # 기기 상태 설정
    log_ref.set(partial_log)
    
    # 상태 업데이트
    set_device_status(device = device, power = power, log = partial_log)

    # 로그 기록
    log_entry = {
        "createdAt": datetime.now().isoformat(),
        "device": device,
        "gesture":gesture,
        "control": control,
        "label" : control_data.get("label"),
        "result": "success" if result.rc == 0 else "mqtt_fail"
    }
    db.reference("log_table").push(log_entry)

    return jsonify({"message" : "전송 성공", "payload" : payload})
