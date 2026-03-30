from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# Общие расширения вынесены отдельно, чтобы избежать циклических импортов.
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
