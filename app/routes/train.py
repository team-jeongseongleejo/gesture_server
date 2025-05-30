from recommand import train_model
from flask import Blueprint, request, jsonify
import firebase_admin
from firebase_admin import db, credentials


if __name__ == "__main__":
    # Firebase 초기화
    cred = credentials.Certificate("../../firebase_config.json")  # ← 너의 Firebase 서비스 계정 JSON 경로로 바꿔줘
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://project1-96997-default-rtdb.asia-southeast1.firebasedatabase.app'  # ← 너의 Firebase DB 주소로 바꿔줘
    })

    # 모델 학습
    train_model()