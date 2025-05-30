from flask import Flask
from firebase_admin import credentials, initialize_app
from .config import Config
from flasgger import Swagger

def create_app():
    app = Flask(__name__)
    #Swagger(app)
    app.config.from_object(Config)

    cred = credentials.Certificate("firebase_config.json")
    initialize_app(cred, {'databaseURL' : app.config['FIREBASE_DB_URL']})

    from app.routes.gesture import gesture_bp
    from app.routes.mode import mode_bp
    from app.routes.status import status_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.recommand import recommand_bp

    app.register_blueprint(gesture_bp)
    app.register_blueprint(mode_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(recommand_bp)

    return app
