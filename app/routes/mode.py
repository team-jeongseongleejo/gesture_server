from flask import Blueprint, request, jsonify
from firebase_admin import db

mode_bp = Blueprint("mode", __name__)
current_mode = {"value" : None}


# 모드 설정
@mode_bp.route("/set_mode", methos=["POST"])
def set_mode():
    data = request.get_json()
    gesture = data.get("gesture")

    if not gesture:
        return jsonify({"error" : "모드 전환 제스처가 없습니다"}), 400
    
    mode_data = db.reference(f"mode_gesture/{gesture}").get()
    if mode_data is None:
        return jsonify({"error": f"mode_gesture/{gesture}에 해당하는 모드드가 없습니다."}), 404
    
    current_mode["value"] = mode_data.get("mode")
    return jsonify({"message" : f"현재 모드가 '{current_mode['value']}'로 설정되었습니다"})