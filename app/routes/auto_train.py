import os
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from firebase_admin import db
from app.routes.recommand import train_model

# 학습 상태 저장 경로
STATE_PATH = "train_state.json"

# 로그 수 기반 임계치 계산
def get_threshold(current_count):
    if current_count < 200:
        return 30
    elif current_count < 500:
        return 100
    else:
        return 200

# 학습 상태 불러오기
def load_train_state():
    if not os.path.exists(STATE_PATH):
        return {"last_count": 0, "last_trained_time": None}
    with open(STATE_PATH, "r") as f:
        return json.load(f)

# 학습 상태 저장
def save_train_state(count):
    state = {
        "last_count": count,
        "last_trained_time": datetime.now().isoformat()
    }
    with open(STATE_PATH, "w") as f:
        json.dump(state, f)

# 로그 및 시간 조건 확인 후 재학습
def check_log_and_train():
    logs = db.reference("log_table").get()
    current_count = len(logs) if logs else 0

    state = load_train_state()
    last_count = state.get("last_count", 0)
    last_time_str = state.get("last_trained_time")
    threshold = get_threshold(current_count)

    now = datetime.now()
    last_time = datetime.fromisoformat(last_time_str) if last_time_str else None
    time_elapsed = (now - last_time) if last_time else None

    # 로그 출력
    if time_elapsed:
        print(f"🔍 로그 수: {current_count}, 이전 학습: {last_count} (+{current_count - last_count}), 시간 경과: {time_elapsed}")
    else:
        print(f"🔍 로그 수: {current_count}, 이전 학습: {last_count} (+{current_count - last_count}), 시간 경과: 최초 실행")

    # 조건 검사
    if (current_count - last_count >= threshold) or (time_elapsed and time_elapsed >= timedelta(hours=3)) or (time_elapsed is None):
        print("✅ 조건 충족 → 모델 재학습 실행")
        train_model()
        save_train_state(current_count)
    else:
        print("⏳ 재학습 조건 미충족")

# 백그라운드 스케줄러 시작
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_log_and_train, 'interval', minutes=10)  # 10분마다 검사
    scheduler.start()
    print("🚀 자동 재학습 스케줄러 시작됨")
