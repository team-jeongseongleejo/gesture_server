from flask import Blueprint, request, jsonify
from firebase_admin import db
from app.routes.mode import current_mode
from flasgger.utils import swag_from
import os

dashboard_bp = Blueprint("dashboard", __name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


# 전체 전자기기 상태 조회
@dashboard_bp.route("/dashboard/devices", methods=["GET"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/dashboard/dashboard_get_devices.yml"))
def get_devices_status():
    status_data = db.reference("status").get()
    return jsonify(status_data or {})


# 현재 모드 조회
@dashboard_bp.route("/dashboard/mode", methods=["GET"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/dashboard/dashboard_get_current_mode.yml"))
def get_current_mode():
    return jsonify({"current_mode": current_mode["value"] or "None"})


# 손동작과 매핑되지 않은 컨트롤(버튼) 목록 조회
@dashboard_bp.route("/dashboard/unmapped_controls", methods=["GET"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/dashboard/dashboard_get_unmapped_controls.yml"))
def get_unmapped_controls():
    mode = request.args.get("mode")
    if not mode:
        return jsonify({"error" : "mode 파라미터가 필요합니다."}), 400
    
    # 가능한 컨트롤(버튼) 목록
    controls_data = db.reference(f"ir_codes/{mode}").get() or {}
    all_controls = set(controls_data.keys())

    # 이미 매핑된 컨트롤(버튼) 목록
    gestures_data = db.reference(f"control_gesture/{mode}").get() or {}
    used_controls = set()
    for g in gestures_data.values():
        if g.get("control"):
            used_controls.add(g["control"])

    unmapped_controls = list(all_controls - used_controls)
    return jsonify(unmapped_controls)


# 제스처 추가 시 선택 가능한 모드 조회
@dashboard_bp.route("/dashboard/modes", methods=["GET"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/dashboard/dashboard_get_modes.yml"))
def get_modes():
    ref = db.reference("ir_codes").get()
    return jsonify(list(ref.keys()) if ref else [])


# 제스처 추가
@dashboard_bp.route("/dashboard/add_gesture", methods=["POST"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/dashboard/dashboard_post_add_gesture.yml"))
def add_gesture():
    data = request.get_json()
    gesture = data.get("gesture")
    mode = data.get("mode")
    control = data.get("control")
    label = data.get("label")

    if not all([gesture, control, label ,mode]):
        return jsonify({"error": "mode, gesture, control, label은 모두 필요합니다."}), 400
    
    # 이미 해당 제스처가 등록되어 있는지 확인
    existing_gesture = db.reference(f"control_gesture/{mode}/{gesture}").get()
    if existing_gesture:
        return jsonify({"error": f"모드 '{mode}'에 제스처 '{gesture}'가 이미 존재합니다."}), 409

    # 존재하는 컨트롤인지 확인 (ir_codes에 등록된 버튼인지)
    ir_code = db.reference(f"ir_codes/{mode}/{control}").get()
    if not ir_code:
        return jsonify({"error": f"control '{control}'은 모드 '{mode}'의 유효한 버튼이 아닙니다."}), 404

    # 컨트롤(버튼)이 이미 다른 제스처에 매핑되어 있는지 확인
    existing_mappings = db.reference(f"control_gesture/{mode}").get() or {}
    for gesture_key, g_data in existing_mappings.items():
        if g_data.get("control") == control:
            return jsonify({"error": f"control '{control}'은 이미 제스처 '{gesture_key}'에 등록되어 있습니다."}), 409


    # 등록
    db.reference(f"control_gesture/{mode}/{gesture}").set({
        "control" : control,
        "label" : label
    })

    return jsonify({
        "message": f"제스처 '{gesture}'가 모드 '{mode}'의 control '{control}'로 등록되었습니다."
    })