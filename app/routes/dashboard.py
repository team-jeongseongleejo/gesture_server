from flask import Blueprint, request, jsonify
from firebase_admin import db
from flasgger.utils import swag_from
from datetime import datetime
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
    mode_gesture = db.reference(f"user_info/current_device").get()
    selected_mode = db.reference(f"mode_gesture/{mode_gesture}/mode").get()
    return jsonify({"current_mode": selected_mode or "None"})

def unmapped_controls_func(mode):
    # 가능한 컨트롤(버튼) 목록
    controls_data = db.reference(f"ir_codes/{mode}").get() or {}
    all_controls = set(controls_data.keys())

    # 이미 매핑된 컨트롤(버튼) 목록
    gestures_data = db.reference(f"control_gesture/{mode}").get() or {}
    used_controls = set()
    for g in gestures_data.values():
        if g.get("control"):
            used_controls.add(g["control"])

    return list(all_controls - used_controls)
    

# 손동작과 매핑되지 않은 컨트롤(버튼) 목록 조회
@dashboard_bp.route("/dashboard/unmapped_controls", methods=["GET"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/dashboard/dashboard_get_unmapped_controls.yml"))
def get_unmapped_controls():
    mode = request.args.get("mode")
    if not mode:
        return jsonify({"error" : "mode 파라미터가 필요합니다."}), 400

    unmapped_controls = unmapped_controls_func(mode)
    return jsonify(unmapped_controls)

def unmapped_gestures_func(mode):
    # 가능한 손동작 목록
    gestures_data = db.reference(f"gesture_list").get() or {}
    all_gestures = set(gestures_data.keys())

    # 이미 매핑된 손동작 목록
    controls_data = db.reference(f"control_gesture/{mode}").get() or {}
    used_gestures = set(controls_data.keys())

    return list(all_gestures - used_gestures)

# 컨트롤(버튼)과 매핑되지 않은 손동작 목록 조회
@dashboard_bp.route("/dashboard/unmapped_gestures", methods=["GET"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/dashboard/dashboard_get_unmapped_gestures.yml"))
def get_unmapped_gestures():
    mode = request.args.get("mode")
    if not mode:
        return jsonify({"error" : "mode 파라미터가 필요합니다."}), 400

    unmapped_gestures = unmapped_gestures_func(mode)
    return jsonify(unmapped_gestures)


# 제스처 추가 시 선택 가능한 모드 조회
@dashboard_bp.route("/dashboard/modes", methods=["GET"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/dashboard/dashboard_get_modes.yml"))
def get_modes():
    ref = db.reference("mode_gesture").get()
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

# 손동작, 컨트롤(버튼) 매핑 정보 등록
@dashboard_bp.route("/dashboard/register_mapping", methods=["POST"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/dashboard/dashboard_post_register_mapping.yml"))
def register_mapping():
    data = request.get_json()
    gesture = data.get("gesture")
    mode = data.get("mode")
    control = data.get("control")

    if not all([gesture, control, mode]):
        return jsonify({"error": "mode, gesture, control은 모두 필요합니다."}), 400
    
    # 매핑되지 않은 손동작인지 확인
    unmapped_gestures = unmapped_gestures_func(mode)
    if gesture not in unmapped_gestures:
        return jsonify({"error": "gesture가 유효하지 않습니다."}), 400

    # 매핑되지 않은 컨트롤인지 확인
    unmapped_controls = unmapped_controls_func(mode)
    if control not in unmapped_controls:
        return jsonify({"error": "control이 유효하지 않습니다."}), 400

    label = db.reference(f"device_list/{mode}/control_list/{control}").get()
    if not label:
        return jsonify({"error": "control_list에 해당 control의 label이 없습니다."}), 500

    # 등록
    db.reference(f"control_gesture/{mode}/{gesture}").set({
        "control" : control,
        "label" : label
    })

    return jsonify({
        "message": f"제스처 '{gesture}'가 모드 '{mode}'의 control '{control}'로 등록되었습니다."
    })    


# 손동작, 컨트롤(버튼) 매핑 정보 수정
@dashboard_bp.route("/dashboard/update_mapping", methods=["POST"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/dashboard/dashboard_post_update_mapping.yml"))
def update_mapping():
    data = request.get_json()
    new_gesture = data.get("new_gesture")
    mode = data.get("mode")
    control = data.get("control")

    if not all([new_gesture, mode, control]):
        return jsonify({"error": "mode, gesture, control은 모두 필요합니다."}), 400
    
    # 매핑되지 않은 손동작인지 확인
    unmapped_gestures = unmapped_gestures_func(mode)
    if new_gesture not in unmapped_gestures:
        return jsonify({"error": "gesture가 이미 매핑되어 있거나 유효하지 않습니다."}), 400

    # 기존 매핑정보 찾기
    gesture_ref = db.reference(f"control_gesture/{mode}")
    mappings = gesture_ref.get() or {}

    old_gesture = None
    label = None
    for gesture, value in mappings.items():
        if value.get("control") == control:
            old_gesture = gesture
            label = value.get("label")
            break
    
    if not old_gesture:
        return jsonify({"error": f"control '{control}'은 '{mode}'에 매핑되어 있지 않습니다."}), 404

    if not label:
        label_data = db.reference(f"device_list/{mode}/control_list/{control}").get()
        label = label_data or "라벨 없음"

    # 새로운 손동작으로 설정
    gesture_ref.child(old_gesture).delete()
    db.reference(f"control_gesture/{mode}/{new_gesture}").set({
        "control" : control,
        "label" : label
    })

    return jsonify({
        "message": f"제스처 '{new_gesture}'가 모드 '{mode}'의 control '{control}'로 등록되었습니다."
    })     

# 기기 이름 변경
@dashboard_bp.route("/dashboard/rename_label", methods=["POST"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/dashboard/dashboard_post_rename_label.yml"))
def rename_label():
    data = request.get_json()
    old_label = data.get("old_label")
    new_label = data.get("new_label")

    if not old_label or not new_label:
        return jsonify({"error": "old_label, new_label가 필요합니다."}), 400
    
    # mode_gesture 수정
    mode_gesture_ref = db.reference("mode_gesture")
    all_mode_gesture = mode_gesture_ref.get() or {}

    for gesture, mode_label in all_mode_gesture.items():
        if isinstance(mode_label, dict):
            if mode_label.get("label") == old_label:
                mode_label["label"] = new_label
                mode_gesture_ref.child(gesture).set(mode_label)

    # device_list 수정
    device_ref = db.reference("device_list")
    all_device = device_ref.get() or {}

    for device_key, value in all_device.items():
        if isinstance(value, dict):
            if value.get("label") == old_label:
                value["label"] = new_label
                device_ref.child(device_key).set(value)
    
    return jsonify({"message": f"'{old_label}' -> '{new_label}'로 이름 변경 완료"})

def parse_time_input(s):
    # 25/05/26 14:30 -> 2025-05-26T14:30:00 변환
    try:
        dt = datetime.strptime(s, "%y/%m/%d %H:%M")
        return dt.isoformat()
    except ValueError:
        return None


# 특정 기간 동안 기기별 제스처 통계
@dashboard_bp.route("/dashboard/device_gesture_stats", methods=["GET"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/dashboard/dashboard_get_device_gesture_stats.yml"))
def get_device_gesture_stats():
    from_input = request.args.get("from") # 25/05/26 14:30
    to_input = request.args.get("to")

    from_iso = parse_time_input(from_input) # 2025-05-26T14:30:00
    to_iso = parse_time_input(to_input)
    print(from_iso)
    print(to_iso)

    if not from_iso or not to_iso:
        return jsonify({"error": "from, to 파라미터는 필수입니다."}), 400
    
    from_time = datetime.fromisoformat(from_iso)
    to_time = datetime.fromisoformat(to_iso)

    if from_time > to_time:
        return jsonify({"error": "'from' 시각은 'to' 시각보다 앞서야 합니다."}), 400

    logs = db.reference("log_table").get() or {}
    device_stats = {}

    for entry in logs.values():
        createdAt = entry.get("createdAt")
        device = entry.get("device")
        gesture = entry.get("gesture")

        if not all([createdAt, device, gesture]):
            continue

        try:
            created_time = datetime.fromisoformat(createdAt)
        except:
            continue

        if not (from_time <= created_time <= to_time):
            continue

        # 기기 별로 기록
        if device not in device_stats:
            device_stats[device] = {
                "total": 0,
                "counts": {}
            }

        stats = device_stats[device]
        stats["counts"][gesture] = stats["counts"].get(gesture, 0) + 1
        stats["total"] += 1
    
    # 비율 계산
    for stats in device_stats.values():
        total = stats["total"]
        stats["ratios"] = {
            gesture: round((count / total) * 100, 1)
            for gesture, count in stats["counts"].items()
        }
    
    payload = {
        "from": from_iso,
        "to": to_iso,
        "device_stats": device_stats
    }
    return jsonify(payload)
