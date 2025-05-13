from flask import Blueprint, request, jsonify
from firebase_admin import db
from app.routes.mode import current_mode
from app.services.mqtt_service import publish_ir

gesture_bp = Blueprint("gesture", __name__)


# 현재 모드에서 제스처 실행
@gesture_bp.route("/gesture", methods=["POST"])
def handle_gesture():
    gesture = request.get_json().get("gesture")
    if not gesture:
        return jsonify({"error": "제스처 값이 없습니다."}), 400
    if not current_mode["value"]:
        return jsonify({"error": "현재 모드가 설정되어 있지 않습니다."}), 400
    
    mode = current_mode["value"]
    control_data = db.reference(f"control_gesture/{mode}/{gesture}").get()
    if control_data is None:
        return jsonify({"error": f"모드 '{mode}'에 제스처 '{gesture}'가 없습니다."}), 404
    
    control = control_data.get("contorl")
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
