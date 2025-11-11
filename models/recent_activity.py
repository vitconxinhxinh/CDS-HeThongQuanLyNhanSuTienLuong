from config import db
from datetime import datetime
from models.employee import Employee

class RecentActivity(db.Model):
    __tablename__ = 'RECENT_ACTIVITY'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('EMPLOYEES.id'))
    action = db.Column(db.String(100))
    detail = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.now)

    employee = db.relationship('Employee', backref='activities')

    def __repr__(self):
        return f'<RecentActivity {self.action} - {self.detail}>'
