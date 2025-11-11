from flask_sqlalchemy import SQLAlchemy

# Thông tin kết nối Oracle
USERNAME = 'system'
PASSWORD = '123456'
HOST = 'localhost'
PORT = '1521'
SID = 'orcl'

SQLALCHEMY_DATABASE_URI = f'oracle+oracledb://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{SID}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

db = SQLAlchemy()
