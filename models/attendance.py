from config import db
from datetime import datetime

class Attendance(db.Model):
    __tablename__ = 'ATTENDANCE'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('EMPLOYEES.id'))
    timestamp = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(10))  # "IN" / "OUT"
    image = db.Column(db.String(255))  # Đường dẫn ảnh chấm công
    # Thống kê giờ/phạt/tăng ca
    late_minutes = db.Column(db.Integer, default=0)
    late_penalty = db.Column(db.Float, default=0.0)
    overtime_minutes = db.Column(db.Integer, default=0)
    overtime_pay = db.Column(db.Float, default=0.0)

    employee = db.relationship('Employee', backref='attendances')

    @property
    def check_in(self):
        """Trả về timestamp nếu đây là bản ghi check-in"""
        return self.timestamp if self.status == 'IN' else None

    @property
    def check_out(self):
        """Trả về timestamp nếu đây là bản ghi check-out"""
        return self.timestamp if self.status == 'OUT' else None

    def __repr__(self):
        return f'<Attendance {self.employee_id} - {self.timestamp} - {self.status}>'
