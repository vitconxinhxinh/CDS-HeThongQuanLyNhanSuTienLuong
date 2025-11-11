from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, date, timedelta
from config import db, SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS
from routes.employee_routes import employee_bp
from routes.payroll_routes import payroll_bp
from models.employee import Employee
from models.department import Department
from models.attendance import Attendance
from sqlalchemy import func, and_
from models.payroll import calculate_salary
from functools import wraps


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-very-secret-key-2025'  
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS

db.init_app(app)

app.register_blueprint(employee_bp, url_prefix='/employee')
app.register_blueprint(payroll_bp)


@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin') and request.endpoint != 'login':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@admin_required
def index():
    # Lấy tổng số nhân viên
    total_employees = Employee.query.count()
    
    # Lấy số nhân viên đi làm hôm nay
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    present_today = db.session.query(func.count(func.distinct(Attendance.employee_id))).filter(
        Attendance.timestamp.between(today_start, today_end),
        Attendance.status == 'IN'
    ).scalar()

    # Tính tỷ lệ đi làm
    attendance_rate = round((present_today / total_employees * 100) if total_employees > 0 else 0)

    # Lấy số phòng ban và số phòng ban có nhân viên
    total_departments = Department.query.count()
    active_departments = db.session.query(func.count(func.distinct(Employee.department_id))).scalar()

    # Lấy tháng/năm từ bộ lọc nếu có
    month_str = request.args.get('month', '')
    if month_str:
        try:
            current_year, current_month = map(int, month_str.split('-'))
        except:
            current_month = today.month
            current_year = today.year
    else:
        current_month = today.month
        current_year = today.year
    total_salary = calculate_salary(current_month, current_year)
    
    # Lấy 5 nhân viên mới nhất và lương thực nhận tháng hiện tại
    recent_employees_raw = Employee.query.order_by(Employee.id.desc()).limit(5).all()
    recent_employees = []
    for emp in recent_employees_raw:
        recent_employees.append(emp)

    # Lấy 5 hoạt động gần đây (chấm công, cập nhật lương, sửa ngày công)
    from models.recent_activity import RecentActivity
    recent_activities = db.session.query(RecentActivity, Employee).join(Employee).order_by(RecentActivity.timestamp.desc()).limit(5).all()
    activity_list = []
    for act, emp in recent_activities:
        time_diff = datetime.now() - act.timestamp
        if time_diff.total_seconds() < 60:
            time_ago = "vừa xong"
        elif time_diff.total_seconds() < 3600:
            time_ago = f"{int(time_diff.total_seconds() / 60)} phút trước"
        else:
            time_ago = f"{int(time_diff.total_seconds() / 3600)} giờ trước"
        activity_list.append({
            'employee': emp,
            'action': act.action,
            'detail': act.detail,
            'time': act.timestamp.strftime('%H:%M'),
            'time_ago': time_ago
        })

    return render_template('index.html',
        total_employees=total_employees,
        present_today=present_today,
        attendance_rate=attendance_rate,
        total_departments=total_departments,
        active_departments=active_departments,
        total_salary=total_salary,
        current_month=current_month,
        current_year=current_year,
        recent_employees=recent_employees,
        recent_activities=activity_list
    )

# Đăng nhập admin
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # Đơn giản: chỉ cho phép admin/admin123
        if username == 'admin' and password == 'admin123':
            session['is_admin'] = True
            flash('Đăng nhập thành công!', 'success')
            return redirect(url_for('employee.attendance_history'))
        else:
            flash('Sai tài khoản hoặc mật khẩu!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    flash('Đã đăng xuất!', 'info')
    return redirect(url_for('login'))

@app.route('/settings')
@admin_required
def settings():
    return render_template('settings.html')

# Báo cáo tổng lương thực nhận từng tháng
@app.route('/salary/report')
@admin_required
def salary_report():
    # Lấy danh sách 12 tháng gần nhất
    now = datetime.now()
    months = []
    for i in range(12):
        m = (now.month - i - 1) % 12 + 1
        y = now.year - ((now.month - i - 1) // 12)
        months.append((y, m))
    months = months[::-1]
    salary_data = []
    for y, m in months:
        total = calculate_salary(m, y)
        salary_data.append({'year': y, 'month': m, 'total': total})
    return render_template('salary_report.html', salary_data=salary_data)

@app.route('/change-password', methods=['POST'])
@admin_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Kiểm tra mật khẩu hiện tại (hardcoded: admin123)
    if current_password != 'admin123':
        flash('Mật khẩu hiện tại không đúng!', 'danger')
        return redirect(url_for('settings'))
    
    if new_password != confirm_password:
        flash('Mật khẩu mới không khớp!', 'danger')
        return redirect(url_for('settings'))
    
    if len(new_password) < 6:
        flash('Mật khẩu mới phải có ít nhất 6 ký tự!', 'danger')
        return redirect(url_for('settings'))
    
    flash('Đổi mật khẩu thành công! (Hiện tại vẫn dùng mật khẩu cũ để đăng nhập)', 'success')
    return redirect(url_for('settings'))

def update_attendance_table():
    """Cập nhật cấu trúc bảng Attendance"""
    try:
        # Kiểm tra xem bảng có tồn tại không
        if not db.inspect(db.engine).has_table("ATTENDANCE"):
            return

        # Kiểm tra cấu trúc hiện tại
        columns = [col['name'] for col in db.inspect(db.engine).get_columns('ATTENDANCE')]
        
        # Nếu đã có cột mới thì không cần update
        if 'check_in' in columns:
            return

        # Tạm thời đổi tên bảng cũ
        db.engine.execute('ALTER TABLE ATTENDANCE RENAME TO ATTENDANCE_OLD')
        
        # Tạo bảng mới
        db.engine.execute('''
            CREATE TABLE ATTENDANCE (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                date DATE NOT NULL,
                check_in DATETIME NOT NULL,
                check_out DATETIME,
                image VARCHAR(255),
                notes VARCHAR(255),
                FOREIGN KEY (employee_id) REFERENCES EMPLOYEES (id)
            )
        ''')
        
        # Copy dữ liệu từ bảng cũ sang bảng mới
        db.engine.execute('''
            INSERT INTO ATTENDANCE (employee_id, date, check_in, image)
            SELECT 
                employee_id,
                date(timestamp),
                timestamp,
                image
            FROM ATTENDANCE_OLD
            WHERE status = 'IN'
        ''')
        
        # Cập nhật check_out từ các bản ghi OUT
        db.engine.execute('''
            UPDATE ATTENDANCE a
            SET check_out = (
                SELECT ao.timestamp
                FROM ATTENDANCE_OLD ao
                WHERE ao.employee_id = a.employee_id
                AND date(ao.timestamp) = a.date
                AND ao.status = 'OUT'
            )
        ''')
        
        # Xóa bảng cũ
        db.engine.execute('DROP TABLE ATTENDANCE_OLD')
        
        print("Đã cập nhật cấu trúc bảng ATTENDANCE thành công!")
        
    except Exception as e:
        print(f"Lỗi khi cập nhật bảng ATTENDANCE: {str(e)}")
        # Rollback nếu có lỗi
        db.session.rollback()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        update_attendance_table()
    app.run(debug=True)
