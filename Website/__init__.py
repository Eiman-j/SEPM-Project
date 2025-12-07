from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path
from flask_login import LoginManager

db = SQLAlchemy()
#DB_NAME = "database.db"

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = ' djedhbcjdhbcxjubcxuduwe' # all flask apps have this variable config
    #always include a database with the following lines.
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:admin@localhost:5432/database' #added postgres
    #username : postgres, pass: admin, database name: database
    db.init_app(app)

    
    # import your blueprints in the init py file
    from .views import views
    from .auth import auth

    # register the blue prints after importing.
    # define the prefix. eg// anything in auth file will be accesed by /auth and then the route
    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    from .models import Users
    print("Calling create_database function...") #debug
    create_database(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login' # where flask should redirect to if user is not logged in
    login_manager.init_app(app) # tells login manager which app is being used

    @login_manager.user_loader
    def load_user(id):
       return Users.query.get(int(id))
    # user.query.get works similar to filter by, except by default it will look for the primary
    #key. so when using get it alwasy looks for the primary key you dont have to specify id=id


    return app

def create_database(app):
    with app.app_context():
        db.create_all()
        print('Ensured all tables are created')

#changed too for postgres