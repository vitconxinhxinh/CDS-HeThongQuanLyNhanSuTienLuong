from datetime import datetime, date
import calendar
from config import db
from models.employee import Employee
from models.attendance import Attendance

class Payroll(db.Model):
    __tablename__ = 'PAYROLLS'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('EMPLOYEES.id'))
    month_year = db.Column(db.String(7), nullable=False)
    base_salary = db.Column(db.Float)
    allowances = db.Column(db.Float)
    overtime = db.Column(db.Float)
    deductions = db.Column(db.Float)
    tax = db.Column(db.Float)
    net_salary = db.Column(db.Float)
    generated_at = db.Column(db.DateTime)

    employee = db.relationship('Employee', backref='payrolls')

def count_standard_workdays(month, year):
    """Đếm số ngày công chuẩn trong tháng (Thứ 2-7, không tính Chủ Nhật)
    
    Args:
        month (int): Tháng
        year (int): Năm
    
    Returns:
        int: Số ngày công chuẩn (26 ngày trong hầu hết tháng)
    """
    workdays = 0
    num_days = calendar.monthrange(year, month)[1]
    
    for day in range(1, num_days + 1):
        # Thứ 2 = 0, Thứ 3 = 1, ..., Thứ 7 = 5, Chủ Nhật = 6
        weekday = date(year, month, day).weekday()
        # Đếm nếu không phải Chủ Nhật (weekday < 6)
        if weekday < 6:
            workdays += 1
    
    return workdays

def count_actual_workdays(employee_id, month, year):
    """Đếm số ngày làm thực tế của nhân viên trong tháng
    (Chỉ tính ngày có đủ check-in và check-out)
    
    Args:
        employee_id (int): ID nhân viên
        month (int): Tháng
        year (int): Năm
    
    Returns:
        int: Số ngày làm thực tế
    """
    start_date = datetime(year, month, 1)
    end_date = datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59)
    
    # Lấy tất cả ngày có check-in
    checkin_dates = set()
    checkins = db.session.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        Attendance.timestamp.between(start_date, end_date),
        Attendance.status == 'IN'
    ).all()
    
    for att in checkins:
        checkin_dates.add(att.timestamp.date())
    
    # Đếm số ngày có cả check-in và check-out
    actual_workdays = 0
    for checkin_day in checkin_dates:
        has_checkout = db.session.query(Attendance).filter(
            Attendance.employee_id == employee_id,
            db.func.trunc(Attendance.timestamp) == checkin_day,
            Attendance.status == 'OUT'
        ).first() is not None
        
        if has_checkout:
            actual_workdays += 1
    
    return actual_workdays

def calculate_salary(month, year):
    """Tính tổng lương của tất cả nhân viên trong tháng
    
    Công thức: Lương = (Lương cơ bản / 26) × Số ngày làm thực tế

    Args:
        month (int): Tháng cần tính lương
        year (int): Năm cần tính lương

    Returns:
        float: Tổng số tiền lương phải trả
    """
    total_salary = 0
    employees = Employee.query.all()
    num_days = calendar.monthrange(year, month)[1]
    standard_workdays = count_standard_workdays(month, year)
    for employee in employees:
        if not employee.base_salary:
            continue
        daily_salary = employee.base_salary / standard_workdays
        salary = 0
        for day in range(1, num_days + 1):
            current_date = date(year, month, day)
            weekday = current_date.weekday()
            # Kiểm tra có đi làm ngày này không
            checkin = db.session.query(Attendance).filter(
                Attendance.employee_id == employee.id,
                db.func.trunc(Attendance.timestamp) == current_date,
                Attendance.status == 'IN'
            ).first()
            checkout = db.session.query(Attendance).filter(
                Attendance.employee_id == employee.id,
                db.func.trunc(Attendance.timestamp) == current_date,
                Attendance.status == 'OUT'
            ).first()
            if checkin and checkout:
                if weekday == 6:  # Chủ nhật
                    salary += daily_salary * 2
                else:
                    salary += daily_salary
        total_salary += salary
    return total_salary

def calculate_employee_salary(employee_id, month, year):
    """Tính lương của một nhân viên cụ thể trong tháng

    Args:
        employee_id (int): ID của nhân viên
        month (int): Tháng cần tính lương
        year (int): Năm cần tính lương

    Returns:
        dict: Thông tin lương gồm số ngày làm việc, lương cơ bản, lương thực nhận, v.v.
    """
    standard_workdays = 26
    
    # Lấy thông tin nhân viên
    employee = Employee.query.get(employee_id)
    if not employee or not employee.base_salary:
        return {
            'workdays_standard': standard_workdays,
            'workdays_actual': 0,
            'base_salary': 0,
            'daily_salary': 0,
            'salary': 0
        }

    # Tính số ngày làm thực tế
    actual_workdays = count_actual_workdays(employee_id, month, year)
    
    # Tính lương theo công thức: (lương cơ bản / 26) × số ngày làm
    daily_salary = employee.base_salary / standard_workdays
    salary = daily_salary * actual_workdays

    return {
        'workdays_standard': standard_workdays,
        'workdays_actual': actual_workdays,
        'base_salary': employee.base_salary,
        'daily_salary': daily_salary,
        'salary': salary
    }

