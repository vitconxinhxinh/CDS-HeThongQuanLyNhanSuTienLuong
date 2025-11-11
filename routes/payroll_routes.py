
import pandas as pd
from flask import send_file, Blueprint, render_template, request, redirect, url_for, flash
from models.employee import Employee
from models.attendance import Attendance
from config import db
from datetime import datetime
import calendar

payroll_bp = Blueprint('payroll', __name__)

@payroll_bp.route('/payroll/export', methods=['GET'])
def export_payroll():
    month = int(request.args.get('month', datetime.now().month))
    year = int(request.args.get('year', datetime.now().year))
    from models.payroll import count_standard_workdays
    num_days = calendar.monthrange(year, month)[1]
    standard_workdays = count_standard_workdays(month, year)
    employees = Employee.query.all()
    data = []
    for emp in employees:
        days = [datetime(year, month, d+1) for d in range(num_days)]
        day_status = []
        total_salary = 0
        daily_salary = emp.base_salary / standard_workdays if emp.base_salary and standard_workdays else 0
        for day in days:
            att_in = Attendance.query.filter(
                Attendance.employee_id == emp.id,
                Attendance.timestamp >= datetime(day.year, day.month, day.day, 0, 0, 0),
                Attendance.timestamp <= datetime(day.year, day.month, day.day, 23, 59, 59),
                Attendance.status == 'IN'
            ).first()
            att_out = Attendance.query.filter(
                Attendance.employee_id == emp.id,
                Attendance.timestamp >= datetime(day.year, day.month, day.day, 0, 0, 0),
                Attendance.timestamp <= datetime(day.year, day.month, day.day, 23, 59, 59),
                Attendance.status == 'OUT'
            ).first()
            if att_in and att_out:
                day_status.append('✓')
                is_sunday = day.weekday() == 6
                if is_sunday:
                    total_salary += daily_salary * 2
                else:
                    total_salary += daily_salary
            else:
                day_status.append('X')
        row = {
            'Tên nhân viên': emp.full_name,
            'Phòng ban': emp.department.name if emp.department else '',
            'Chức vụ': emp.position,
            'Lương (VNĐ)': total_salary
        }
        for i, status in enumerate(day_status, 1):
            row[f'Ngày {i}'] = status
        data.append(row)
    df = pd.DataFrame(data)
    file_path = f'payroll_{month}_{year}.xlsx'
    df.to_excel(file_path, index=False)
    return send_file(file_path, as_attachment=True)

@payroll_bp.route('/payroll/update', methods=['POST'])
def update_payroll():
    employee_name = request.form.get('employee_name')
    employee = Employee.query.filter_by(full_name=employee_name).first()
    month = int(request.args.get('month', datetime.now().month))
    year = int(request.args.get('year', datetime.now().year))
    num_days = calendar.monthrange(year, month)[1]
    if not employee:
        flash('Không tìm thấy nhân viên.', 'danger')
        return redirect(url_for('payroll.payroll'))
    try:
        for d in range(1, num_days+1):
            status = request.form.get(f'day_status_{d}')
            day_date = datetime(year, month, d)
            Attendance.query.filter(
                Attendance.employee_id == employee.id,
                Attendance.timestamp >= datetime(day_date.year, day_date.month, day_date.day, 0, 0, 0),
                Attendance.timestamp <= datetime(day_date.year, day_date.month, day_date.day, 23, 59, 59)
            ).delete()
            if status == '✓':
                att_in = Attendance(employee_id=employee.id, timestamp=datetime(year, month, d, 8, 0, 0), status='IN')
                att_out = Attendance(employee_id=employee.id, timestamp=datetime(year, month, d, 17, 0, 0), status='OUT')
                db.session.add(att_in)
                db.session.add(att_out)
        db.session.commit()
        # Lưu hoạt động gần đây
        try:
            from models.recent_activity import RecentActivity
            activity = RecentActivity(
                employee_id=employee.id,
                action=f'Cập nhật ngày công tháng {month}/{year}',
                timestamp=datetime.now()
            )
            db.session.add(activity)
            db.session.commit()
        except Exception:
            pass
        flash('Cập nhật ngày đi làm thành công!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Lỗi khi cập nhật ngày đi làm: ' + str(e), 'danger')
    return redirect(url_for('payroll.payroll'))
from models.employee import Employee
from models.attendance import Attendance
from datetime import datetime
import calendar


@payroll_bp.route('/payroll', methods=['GET'])
def payroll():
    # Lấy tháng/năm từ query, mặc định là tháng/năm hiện tại
    month = int(request.args.get('month', datetime.now().month))
    year = int(request.args.get('year', datetime.now().year))
    num_days = calendar.monthrange(year, month)[1]
    employees = Employee.query.all()
    payroll_data = []
    for emp in employees:
        days = [datetime(year, month, d+1) for d in range(num_days)]
        day_status = []
        workdays_normal = 0
        workdays_sunday = 0
        for day in days:
            att_in = Attendance.query.filter(
                Attendance.employee_id == emp.id,
                Attendance.timestamp >= datetime(day.year, day.month, day.day, 0, 0, 0),
                Attendance.timestamp <= datetime(day.year, day.month, day.day, 23, 59, 59),
                Attendance.status == 'IN'
            ).first()
            att_out = Attendance.query.filter(
                Attendance.employee_id == emp.id,
                Attendance.timestamp >= datetime(day.year, day.month, day.day, 0, 0, 0),
                Attendance.timestamp <= datetime(day.year, day.month, day.day, 23, 59, 59),
                Attendance.status == 'OUT'
            ).first()
            if att_in and att_out:
                day_status.append('✓')
                if day.weekday() == 6:
                    workdays_sunday += 1
                else:
                    workdays_normal += 1
            else:
                day_status.append('X')
        # Số ngày công chuẩn (không tính chủ nhật)
        standard_workdays = sum(1 for d in days if d.weekday() != 6)
        salary_per_day = emp.base_salary / standard_workdays if emp.base_salary and standard_workdays > 0 else 0
        total_salary = salary_per_day * workdays_normal + salary_per_day * 2 * workdays_sunday
        payroll_data.append({
            'name': emp.full_name,
            'department': emp.department.name if emp.department else '',
            'position': emp.position,
            'days': day_status,
            'total_salary': total_salary
        })
    # Tạo danh sách các ngày chủ nhật trong tháng
    sundays = []
    for d in range(1, num_days+1):
        day = datetime(year, month, d)
        if day.weekday() == 6:  # 6 = Sunday
            sundays.append(d)
    return render_template('payroll.html', payroll_data=payroll_data, month=month, year=year, num_days=num_days, sundays=sundays)