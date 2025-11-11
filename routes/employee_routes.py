from models.recent_activity import RecentActivity
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from config import db
from models.employee import Employee
from models.attendance import Attendance
from models.face_encoding import FaceEncoding
from datetime import datetime
import os
import base64
import io
import numpy as np
from PIL import Image
import face_recognition
from werkzeug.utils import secure_filename
import cv2
from functools import wraps

employee_bp = Blueprint('employee', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin') and request.endpoint != 'login':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# API trả về encoding và tên nhân viên cho nhận diện realtime
@employee_bp.route('/api/face-encodings', methods=['GET'])
def api_face_encodings():
    # Lấy tất cả encoding và tên nhân viên
    faces = FaceEncoding.query.all()
    data = []
    for face in faces:
        emp = Employee.query.get(face.employee_id)
        if emp:
            data.append({
                'employee_id': emp.id,
                'name': emp.full_name,
                'department': emp.department.name if emp.department else '',
                'position': emp.position,
                'encoding': list(np.frombuffer(face.encoding, dtype=np.float64))
            })
    return jsonify(data)
    # Sửa nhân viên
    # Xóa nhân viên
    # Route lịch sử chấm công
    # Trang chấm công bằng camera
    # Trang danh sách nhân viên
    # Thêm nhân viên (ảnh upload hoặc camera)

# === Sửa nhân viên ===
@employee_bp.route('/edit/<int:emp_id>', methods=['POST'])
def edit_employee(emp_id):
    emp = Employee.query.get(emp_id)
    if not emp:
        flash('Không tìm thấy nhân viên!', 'danger')
        return redirect(url_for('employee.list_employees'))
    name = request.form.get('name')
    dept = request.form.get('department')
    pos = request.form.get('position')
    try:
        salary = float(request.form.get('salary', 0))
    except:
        salary = 0.0
    emp.full_name = name
    emp.position = pos
    emp.base_salary = salary
    # Cập nhật phòng ban
    department_obj = None
    if dept:
        from models.department import Department
        department_obj = Department.query.filter_by(name=dept).first()
        if not department_obj:
            department_obj = Department(name=dept)
            db.session.add(department_obj)
            db.session.commit()
    emp.department_id = department_obj.id if department_obj else None
    db.session.commit()
    # Ghi nhận hoạt động cập nhật lương
    activity = RecentActivity(
        employee_id=emp.id,
        action='Update Salary',
        detail=f'Cập nhật lương: {emp.base_salary}',
        timestamp=datetime.now()
    )
    db.session.add(activity)
    db.session.commit()
    flash('Đã cập nhật thông tin nhân viên!', 'success')
    return redirect(url_for('employee.list_employees'))

# === Xóa nhân viên ===
@employee_bp.route('/delete/<int:emp_id>', methods=['POST'])
def delete_employee(emp_id):
    emp = Employee.query.get(emp_id)
    if not emp:
        flash('Không tìm thấy nhân viên!', 'danger')
        return redirect(url_for('employee.list_employees'))
    # Xóa tất cả bản ghi Attendance liên quan
    Attendance.query.filter_by(employee_id=emp.id).delete()
    # Xóa tất cả bản ghi FaceEncoding liên quan
    FaceEncoding.query.filter_by(employee_id=emp.id).delete()
    db.session.delete(emp)
    db.session.commit()
    flash('Đã xóa nhân viên!', 'success')
    return redirect(url_for('employee.list_employees'))

# === Route lịch sử chấm công ===
@employee_bp.route('/attendance/history')
@admin_required
def attendance_history():
    search = request.args.get('search', '').strip()
    date_str = request.args.get('date', '').strip()
    month_str = request.args.get('month', '').strip()
    query = Attendance.query.join(Employee)
    if search:
        query = query.filter(Employee.full_name.ilike(f'%{search}%'))
    if month_str:
        try:
            from datetime import datetime
            year, month = map(int, month_str.split('-'))
            start = datetime(year, month, 1)
            if month == 12:
                end = datetime(year + 1, 1, 1)
            else:
                end = datetime(year, month + 1, 1)
            query = query.filter(Attendance.timestamp >= start, Attendance.timestamp < end)
        except:
            pass
    elif date_str:
        try:
            from datetime import datetime, timedelta
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            start = datetime.combine(date_obj.date(), datetime.min.time())
            end = datetime.combine(date_obj.date(), datetime.max.time())
            query = query.filter(Attendance.timestamp.between(start, end))
        except:
            pass
    attendances = query.order_by(Attendance.timestamp.desc()).limit(100).all()
    return render_template('attendance_history.html', attendances=attendances, search=search)

# === Route chỉnh sửa chấm công (admin) ===
@employee_bp.route('/attendance/edit/<int:att_id>', methods=['GET', 'POST'])
def edit_attendance(att_id):
    att = Attendance.query.get(att_id)
    if not att:
        flash('Không tìm thấy bản ghi chấm công!', 'danger')
        return redirect(url_for('employee.attendance_history'))
    if request.method == 'POST':
        # Chỉ cho phép admin (giả sử có biến session['is_admin'])
        from flask import session
        if not session.get('is_admin'):
            flash('Bạn không có quyền chỉnh sửa!', 'danger')
            return redirect(url_for('employee.attendance_history'))
        # Cập nhật các trường
        try:
            att.timestamp = datetime.strptime(request.form.get('timestamp'), '%Y-%m-%d %H:%M:%S')
        except:
            pass
        att.status = request.form.get('status', att.status)
        att.late_minutes = int(request.form.get('late_minutes', att.late_minutes or 0))
        att.late_penalty = float(request.form.get('late_penalty', att.late_penalty or 0))
        att.overtime_minutes = int(request.form.get('overtime_minutes', att.overtime_minutes or 0))
        att.overtime_pay = float(request.form.get('overtime_pay', att.overtime_pay or 0))
        att.image = request.form.get('image', att.image)
        att.reason = request.form.get('reason', getattr(att, 'reason', ''))
        db.session.commit()
        flash('Đã cập nhật bản ghi chấm công!', 'success')
        return redirect(url_for('employee.attendance_history'))
    return render_template('edit_attendance.html', att=att)

# === Trang chấm công bằng camera ===
@employee_bp.route('/attendance/camera', methods=['GET', 'POST'])
@admin_required
def attendance_camera():
    if request.method == 'POST':
        image_base64 = request.form.get('image_base64')
        if not image_base64:
            flash("Không nhận được ảnh từ camera!", "danger")
            return redirect(url_for('employee.attendance_camera'))
        # ...existing code...
        # Sau khi nhận diện khuôn mặt, xác định employee
        # Giả sử có biến employee_id hoặc employee đã xác định ở đoạn nhận diện
        # Ví dụ: employee = Employee.query.get(employee_id)
        # Nếu chưa có, cần lấy employee từ kết quả nhận diện
        # ...
        # Nếu đã xác định employee:
        if 'employee' in locals() and employee:
            activity = RecentActivity(
                employee_id=employee.id,
                action='Check-in',
                detail=f'Chấm công thành công lúc {datetime.now().strftime("%H:%M %d/%m/%Y")}',
                timestamp=datetime.now()
            )
            db.session.add(activity)
            db.session.commit()
        header, encoded = image_base64.split(',', 1)
        img_bytes = base64.b64decode(encoded)
        pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img_np = np.array(pil_img, dtype=np.uint8)
        # Resize nếu quá lớn
        max_width = 640
        # ...existing code...
        if img_np.shape[1] > max_width:
            scale = max_width / img_np.shape[1]
            new_size = (int(img_np.shape[1] * scale), int(img_np.shape[0] * scale))
            img_np = cv2.resize(img_np, new_size, interpolation=cv2.INTER_AREA)
        # Đảm bảo đúng kiểu
        if img_np.ndim == 2:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
        elif img_np.shape[2] == 4:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)
        else:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        img_np = np.ascontiguousarray(img_np, dtype=np.uint8)
        # Nhận diện khuôn mặt
        # ...existing code...
        face_locations = face_recognition.face_locations(img_np, model='hog')
        if len(face_locations) == 0:
            flash("Không phát hiện được khuôn mặt!", "warning")
            return redirect(url_for('employee.list_employees'))
        encodings = face_recognition.face_encodings(img_np, face_locations)
        if not encodings:
            flash("Không thể mã hóa khuôn mặt!", "danger")
            return redirect(url_for('employee.list_employees'))
        # So sánh với DB
        known_faces = FaceEncoding.query.all()
        matched_emp_id = None
        for face in known_faces:
            known_encoding = np.frombuffer(face.encoding, dtype=np.float64)
            matches = face_recognition.compare_faces([known_encoding], encodings[0], tolerance=0.5)
            if matches[0]:
                matched_emp_id = face.employee_id
                break
        if matched_emp_id:
            # Chỉ lưu ảnh nếu điểm danh thành công
            save_dir = os.path.join('static', 'attendance_images')
            os.makedirs(save_dir, exist_ok=True)
            filename = f"attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            image_path = os.path.join(save_dir, filename)
            pil_img.save(image_path, format='JPEG')
            rel_path = image_path.replace('\\', '/').replace('\\', '/')
            emp = Employee.query.filter_by(id=matched_emp_id).first()
            if emp:
                from datetime import time
                today = datetime.now().date()
                # Lấy tất cả bản ghi chấm công hôm nay của nhân viên
                today_att = Attendance.query.filter(
                    Attendance.employee_id == emp.id,
                    Attendance.timestamp >= datetime.combine(today, time.min),
                    Attendance.timestamp <= datetime.combine(today, time.max)
                ).order_by(Attendance.timestamp).all()
                if len(today_att) == 0:
                    # Lần đầu: IN
                    # Tính trễ: lịch làm việc cố định 08:00 - 18:00
                    from math import ceil
                    work_start = time(8, 0)
                    now_dt = datetime.now()
                    late_minutes = 0
                    late_penalty = 0.0
                    if now_dt.time() > work_start:
                        delta = datetime.combine(now_dt.date(), now_dt.time()) - datetime.combine(now_dt.date(), work_start)
                        late_minutes = int(delta.total_seconds() // 60)
                        # Mỗi 20 phút trễ bị phạt 50,000 (làm tròn lên mỗi khoảng 20 phút)
                        if late_minutes > 0:
                            intervals = ceil(late_minutes / 20)
                            late_penalty = intervals * 50000

                    att = Attendance(
                        employee_id=emp.id,
                        timestamp=now_dt,
                        status="IN",
                        image=rel_path,
                        late_minutes=late_minutes,
                        late_penalty=late_penalty
                    )
                    db.session.add(att)
                    db.session.commit()
                    # Ghi nhận hoạt động chấm công thành công
                    activity = RecentActivity(
                        employee_id=emp.id,
                        action='Check-in',
                        detail=f'Chấm công thành công lúc {now_dt.strftime("%H:%M %d/%m/%Y")}',
                        timestamp=now_dt
                    )
                    db.session.add(activity)
                    db.session.commit()
                    if late_minutes > 0:
                        flash(f"✅ Chấm công (IN) cho {emp.full_name} — Trễ {late_minutes} phút, phạt {late_penalty:,.0f} VND", "warning")
                    else:
                        flash(f"✅ Chấm công (IN) thành công cho {emp.full_name}", "success")
                elif len(today_att) == 1:
                    # Lần 2: OUT
                    now_dt = datetime.now()
                    work_end = time(18, 0)
                    overtime_minutes = 0
                    overtime_pay = 0.0

                    if now_dt.time() > work_end:
                        delta = datetime.combine(now_dt.date(), now_dt.time()) - datetime.combine(now_dt.date(), work_end)
                        overtime_minutes = int(delta.total_seconds() // 60)

                        # Tính lương cơ bản theo ngày -> mặc định lấy từ salary_type
                        def compute_daily_salary(emp_obj):
                            # Giả định: nếu salary_type == 'monthly' thì base_salary là lương tháng, chia 30 để ra ngày
                            try:
                                st = getattr(emp_obj, 'salary_type', 'monthly') or 'monthly'
                            except:
                                st = 'monthly'
                            if st == 'daily':
                                return emp_obj.base_salary or 0.0
                            # mặc định monthly
                            return (emp_obj.base_salary or 0.0) / 30.0

                        daily_salary = compute_daily_salary(emp)
                        hourly_base = (daily_salary / 24.0) if daily_salary else 0.0
                        overtime_hours = overtime_minutes / 60.0
                        overtime_pay = overtime_hours * hourly_base * 1.5

                    att = Attendance(
                        employee_id=emp.id,
                        timestamp=now_dt,
                        status="OUT",
                        image=rel_path,
                        overtime_minutes=overtime_minutes,
                        overtime_pay=round(overtime_pay, 2)
                    )
                    db.session.add(att)
                    db.session.commit()
                    if overtime_minutes > 0:
                        flash(f"✅ Chấm công (OUT) cho {emp.full_name} — Tăng ca {overtime_minutes} phút, phụ cấp {overtime_pay:,.0f} VND", "success")
                    else:
                        flash(f"✅ Chấm công (OUT) thành công cho {emp.full_name}", "success")
                else:
                    flash(f"❌ Mỗi ngày chỉ được chấm công 2 lần (IN/OUT)!", "warning")
            else:
                flash("Không tìm thấy nhân viên tương ứng!", "danger")
        else:
            flash("Không nhận diện được khuôn mặt!", "warning")
        return redirect(url_for('employee.list_employees'))
    return render_template('attendance_camera.html')


# === Trang danh sách nhân viên ===
@employee_bp.route('/employees')
@admin_required
def list_employees():
    employees = Employee.query.all()
    return render_template('employees.html', employees=employees, now=datetime.now)


# === Thêm nhân viên (ảnh upload hoặc camera) ===
@employee_bp.route('/add', methods=['POST'])
def add_employee():
    name = request.form.get('name')
    dept = request.form.get('department')
    pos = request.form.get('position')
    try:
        salary = float(request.form.get('salary', 0))
    except:
        salary = 0.0

    image_file = request.files.get('image')
    image_base64 = request.form.get('image_base64')

    save_dir = os.path.join('static', 'employee_images')
    os.makedirs(save_dir, exist_ok=True)
    image_path = None
    encodings = None

    try:
        # === 1️⃣ Lấy ảnh từ camera hoặc upload ===
        if image_base64:
            header, encoded = image_base64.split(',', 1)
            img_bytes = base64.b64decode(encoded)
            filename = f"camera_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
            image_path = os.path.join(save_dir, filename)

            pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            pil_img.save(image_path, format='JPEG')
            img_np = np.array(pil_img, dtype=np.uint8)
            print("DEBUG base64 image:", img_np.shape, img_np.dtype)

        elif image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            name_root, ext = os.path.splitext(filename)
            if ext.lower() not in ['.jpg', '.jpeg', '.png']:
                filename = f"{name_root}.jpg"
            image_path = os.path.join(save_dir, filename)

            pil_img = Image.open(image_file).convert("RGB")
            pil_img.save(image_path, format='JPEG')
            img_np = np.array(pil_img, dtype=np.uint8)
            print("DEBUG upload image:", img_np.shape, img_np.dtype)
        else:
            flash("Vui lòng tải ảnh hoặc chụp ảnh nhân viên!", "warning")
            return redirect(url_for('employee.list_employees'))

        # === 2️⃣ Resize nếu quá lớn ===
        max_width = 640
        if img_np.shape[1] > max_width:
            scale = max_width / img_np.shape[1]
            new_size = (int(img_np.shape[1] * scale), int(img_np.shape[0] * scale))
            img_np = cv2.resize(img_np, new_size, interpolation=cv2.INTER_AREA)
            print("Ảnh đã resize:", img_np.shape)

        # === 3️⃣ Đảm bảo dữ liệu ảnh đúng kiểu cho dlib 19.24 ===
        if img_np.ndim == 2:  # grayscale
            img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
        elif img_np.shape[2] == 4:  # RGBA
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)
        else:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)

        # ép kiểu contiguous (bộ nhớ liền mạch, tránh lỗi “Unsupported image type”)
        img_np = np.ascontiguousarray(img_np, dtype=np.uint8)

        # === 4️⃣ Phát hiện khuôn mặt bằng face_recognition ===
        face_locations = face_recognition.face_locations(img_np, model='hog')  # dùng HOG cho nhanh
        print(f"DEBUG face_locations: {len(face_locations)} khuôn mặt được phát hiện")

        if len(face_locations) == 0:
            flash("Không phát hiện được khuôn mặt trong ảnh!", "danger")
            return redirect(url_for('employee.list_employees'))

        # === 5️⃣ Mã hóa khuôn mặt ===
        encodings = face_recognition.face_encodings(img_np, face_locations)
        if not encodings:
            flash("Không thể tạo mã nhận diện khuôn mặt!", "danger")
            return redirect(url_for('employee.list_employees'))

        # === 6️⃣ Lưu dữ liệu vào DB ===
        rel_path = image_path.replace('\\', '/')
        department_obj = None
        if dept:
            from models.department import Department
            department_obj = Department.query.filter_by(name=dept).first()
            if not department_obj:
                department_obj = Department(name=dept)
                db.session.add(department_obj)
                db.session.commit()
        new_emp = Employee(
            employee_code=f"EMP{datetime.now().strftime('%Y%m%d%H%M%S')}",
            full_name=name,
            position=pos,
            base_salary=salary,
            department_id=department_obj.id if department_obj else None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            active='1'
        )

        
        db.session.add(new_emp)
        db.session.commit()

        enc0 = np.array(encodings[0], dtype=np.float64)
        face_enc = FaceEncoding(
            employee_id=new_emp.id,
            encoding=enc0.tobytes(),
            created_at=datetime.now()
        )
        db.session.add(face_enc)
        db.session.commit()

        new_emp.image = rel_path
        db.session.commit()

        flash("✅ Thêm nhân viên và nhận diện khuôn mặt thành công!", "success")
        return redirect(url_for('employee.list_employees'))

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Lỗi nhận diện khuôn mặt: {e}", "danger")
        return redirect(url_for('employee.list_employees'))
