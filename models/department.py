from config import db

class Department(db.Model):
    __tablename__ = 'DEPARTMENTS'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    note = db.Column(db.String(255))

    def __repr__(self):
        return f'<Department {self.name}>'
