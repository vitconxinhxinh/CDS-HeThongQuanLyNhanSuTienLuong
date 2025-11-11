
from config import db
from models.department import Department

class Employee(db.Model):
    __tablename__ = 'EMPLOYEES'

    id = db.Column(db.Integer, primary_key=True)
    employee_code = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(150))
    phone = db.Column(db.String(50))
    department_id = db.Column(db.Integer, db.ForeignKey('DEPARTMENTS.id'))
    position = db.Column(db.String(100))
    base_salary = db.Column(db.Float, default=0)
    salary_type = db.Column(db.String(20), default='monthly')
    hire_date = db.Column(db.Date)
    active = db.Column(db.String(1), default='1')
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)

    department = db.relationship('Department', backref='employees')

    @property
    def name(self):
        """Alias for full_name to maintain compatibility"""
        return self.full_name

    @property
    def salary(self):
        """Alias for base_salary to maintain compatibility"""
        return self.base_salary

    @property
    def image_path(self):
        """Return path to employee image if exists"""
        return f'employee_images/{self.id}.jpg'

    def __repr__(self):
        return f'<Employee {self.full_name}>'

    def __repr__(self):
        return f'<Employee {self.full_name}>'
