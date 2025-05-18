from flask import Blueprint, request, jsonify
from firebase_admin import db
from app.routes.mode import current_mode
from app.services.mqtt_service import publish_ir
from flasgger.utils import swag_from
import os

gesture_bp = Blueprint("gesture", __name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


# 현재 모드에서 제스처 실행
@gesture_bp.route("/gesture", methods=["POST"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/gesture/gesture_post_handle_gesture.yml"))
def handle_gesture():
    gesture = request.get_json().get("gesture")
    if not gesture:
        return jsonify({"error": "제스처 값이 없습니다."}), 400
    
    mode_data = db.reference(f"mode_gesture/{gesture}").get()
    selected_mode = mode_data.get("mode") if mode_data else None

    # 모드 설정
    if selected_mode:
        # 모드 선택
        if not current_mode["value"]:
            current_mode["value"] = selected_mode
            return jsonify({"message": f"모드 '{selected_mode}'로 설정되었습니다."})
        # 모드 해제
        elif current_mode["value"] == selected_mode:
            current_mode["value"] = None
            return jsonify({"message": f"모드 '{selected_mode}'가 해제되었습니다."})
        # 모드 전환
        else:
            prev = current_mode["value"]
            current_mode["value"] = selected_mode
            return jsonify({"message": f"모드 '{prev}'->'{selected_mode}'로 전환되었습니다."})

    if not current_mode["value"]:
        return jsonify({"error": "현재 모드가 설정되어 있지 않습니다."}), 400

    mode = current_mode["value"]
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
    
    return jsonify({"message" : "전송 성공", "payload" : payload})
