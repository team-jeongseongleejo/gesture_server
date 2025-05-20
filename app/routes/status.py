from flask import Blueprint, request, jsonify
from firebase_admin import db
from flasgger.utils import swag_from
import os

status_bp = Blueprint("status", __name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

# 특정 전자기기 상태 조회
@status_bp.route("/get_status", methods=["GET"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/status/status_get_status.yml"))
def get_status():
    device = request.args.get("device")
    if not device:
        return jsonify({"error" : "device 파라미터가 필요합니다."}), 400
    
    status = db.reference(f"status/{device}").get()
    if status is None:
        return jsonify({"error" : f"{device}의 상태 정보가 업습니다."}), 404
    
    return jsonify(status)


# 특정 전자기기 상태 설정
def set_device_status(device, power, log):
    db.reference(f"status/{device}/power").set(power)
    db.reference(f"status/{device}/log").update(log)

@status_bp.route("/set_status", methods=["POST"])
@swag_from(os.path.join(BASE_DIR, "docs/swagger/status/status_post_set_status.yml"))
def set_status():
    data = request.get_json()
    device = data.get("device")
    power = data.get("power")
    log = data.get("log")

    if not all([device, power, log]):
        return jsonify({"error" : "device, power, log가 모두 필요합니다."}), 400
    
    #db.reference(f"status/{device}").update({
    #    "power" : power,
    #    "log" : log
    #})
    set_device_status(device, power, log)

    return jsonify({"message" : f"{device} 상태가 업데이트 되었습니다."})