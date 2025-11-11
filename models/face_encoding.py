from config import db

class FaceEncoding(db.Model):
    __tablename__ = 'FACE_ENCODINGS'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('EMPLOYEES.id'))
    encoding = db.Column(db.LargeBinary)
    created_at = db.Column(db.DateTime)

    employee = db.relationship('Employee', backref='face_encodings')
