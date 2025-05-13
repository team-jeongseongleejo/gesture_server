```
gesture_server/
│
├── app/
│   ├── __init__.py
│   ├── routes/
│   │   ├── gesture.py
│   │   ├── mode.py
│   │   ├── status.py
│   │   └── dashboard.py
│   ├── services/
│   │   └── mqtt_service.py
│   └── config.py          ← 환경 설정 (예: Firebase URL 등)
│
├── firebase_config.json   ← Firebase 키
├── run.py
├── .gitignore
└── requirements.txt
```