from flask import Blueprint, request, jsonify
from firebase_admin import db
from app.routes.status import set_device_status
from app.services.mqtt_service import publish_ir
from flasgger.utils import swag_from
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
        }
    }

    # 현재 상태 가져오기
    current_power = db.reference(f"status/{device}/power").get() or "off"
    log_data = db.reference(f"status/{device}/log").get()
    current_log = log_data if isinstance(log_data, dict) else {}

    # power 설정
    if control == "power":
        power = "off" if current_power == "on" else "on"
        return power, {"power": power}
    
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

    log_ref = db.reference(f"status/{device}/log")
    # light 상태 설정
    if device == "light":
        if control == "color":
            log_ref.set(partial_log)
        else:
            current_log = log_ref.get() or {}
            color = current_log.get("color")
            if color:
                partial_log["color"] = color
            log_ref.set(partial_log)
    # 그 외 기기 상태 설정
    else:
        log_ref.set(partial_log)    
    
    # 상태 업데이트
    set_device_status(device = device, power = power, log = partial_log)
    return jsonify({"message" : "전송 성공", "payload" : payload})
