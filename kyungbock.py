# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from supabase import create_client
from dotenv import load_dotenv
from functools import wraps
from datetime import date, datetime, timedelta
from io import BytesIO
import os, base64, random, string

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-key")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    print("WARNING: SUPABASE_URL / SUPABASE_ANON_KEY가 .env에 없습니다.")

sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY) if SUPABASE_URL and SUPABASE_ANON_KEY else None
admin_sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY) if SUPABASE_URL and SUPABASE_SERVICE_KEY else None

FESTIVAL_NAME = "북악제"
FESTIVAL_SLOGAN = "빛나는 우리, 하나의 이야기"
FESTIVAL_DATE = date(2026, 10, 30)

SITE_INFO = {
    "phone": "학교 문의처",
    "email": "학교 이메일",
    "hours": "축제 운영시간",
    "address": "서울특별시 종로구 경복궁 인근",
    "subway": "지하철 이용 정보",
    "bus": "버스 이용 정보",
    "walk": "도보 이용 정보",
}

def db():
    return sb

def write_db():
    return admin_sb or sb

def friendly(e):
    return str(e)

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            flash("로그인이 필요합니다.", "error")
            return redirect(url_for("login"))
        if not user.get("is_admin"):
            flash("관리자 권한이 없습니다.", "error")
            return redirect(url_for("home"))
        if admin_sb is None:
            flash("SUPABASE_SERVICE_KEY가 설정되지 않아 관리자 변경 기능을 사용할 수 없습니다.", "error")
            return redirect(url_for("home"))
        return fn(*args, **kwargs)
    return wrapper

def current_user():
    uid = session.get("user_id")
    if not uid or not sb:
        return None
    try:
        res = db().table("profiles").select("*").eq("id", uid).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None

def login_user(uid):
    session["user_id"] = uid
    session.permanent = True

def logout_user():
    session.clear()

def record_visit():
    if session.get("visit_recorded"):
        return
    session["visit_recorded"] = True
    try:
        db().table("visits").insert({}).execute()
    except Exception:
        pass

def fetch_notices():
    try:
        res = db().table("notices").select("*").order("created_at", desc=True).execute()
        return [{
            "id": r["id"], "title": r.get("title") or "", "content": r.get("content") or "",
            "new": bool(r.get("is_new")), "date": (r.get("created_at") or "")[:10]
        } for r in (res.data or [])]
    except Exception:
        return []

def fetch_booths():
    try:
        res = db().table("booths").select("*").order("created_at", desc=True).execute()
        return [{
            "id": r["id"], "name": r.get("name") or "", "category": r.get("category") or "",
            "place": r.get("place") or "", "hours": r.get("hours") or "",
            "desc": r.get("description") or "", "icon": r.get("icon") or "🏪",
            "image": r.get("image")
        } for r in (res.data or [])]
    except Exception:
        return []

def fetch_programs():
    try:
        res = db().table("programs").select("*").order("created_at", desc=True).execute()
        return [{
            "id": r["id"], "name": r.get("name") or "", "category": r.get("category") or "기타",
            "date": r.get("program_date") or "", "time": r.get("program_time") or "",
            "place": r.get("place") or "", "desc": r.get("description") or "",
            "icon": r.get("icon") or "🎫"
        } for r in (res.data or [])]
    except Exception:
        return []

def fetch_schedule():
    try:
        res = db().table("schedule").select("*").order("day").order("time").execute()
        rows = res.data or []
        grouped = {}
        for r in rows:
            grouped.setdefault(r.get("day") or "", []).append(r)
        return grouped
    except Exception:
        return {}

@app.context_processor
def inject_globals():
    return {
        "festival_name": FESTIVAL_NAME,
        "festival_slogan": FESTIVAL_SLOGAN,
        "festival_date": FESTIVAL_DATE,
        "user": current_user(),
        "site_info": SITE_INFO,
    }

@app.before_request
def before():
    if request.endpoint != "static":
        record_visit()

@app.route("/")
def home():
    return render_template("index.html",
                           notices=fetch_notices()[:4],
                           booths=fetch_booths()[:4],
                           schedule=fetch_schedule())

@app.route("/intro")
def intro():
    return render_template("intro.html")

@app.route("/greeting")
def greeting():
    return render_template("greeting.html")

@app.route("/programs")
def programs():
    cat = request.args.get("category", "전체")
    all_programs = fetch_programs()
    filtered = all_programs if cat == "전체" else [p for p in all_programs if p["category"] == cat]
    return render_template("programs.html", programs=filtered, category=cat)

@app.route("/programs/add", methods=["GET", "POST"])
@admin_required
def program_add():
    if request.method == "POST":
        data = {
            "name": request.form.get("name", "").strip(),
            "category": request.form.get("category", "기타"),
            "program_date": request.form.get("date", "").strip(),
            "program_time": request.form.get("time", "").strip(),
            "place": request.form.get("place", "").strip(),
            "description": request.form.get("description", "").strip(),
            "icon": request.form.get("icon", "🎫").strip() or "🎫",
        }
        if not data["name"]:
            flash("프로그램 이름을 입력해주세요.", "error")
        else:
            try:
                write_db().table("programs").insert(data).execute()
                flash("프로그램이 등록되었습니다.", "success")
                return redirect(url_for("programs"))
            except Exception as e:
                flash(friendly(e), "error")
    return render_template("program_form.html", item=None)

@app.route("/programs/<item_id>/edit", methods=["POST"])
@admin_required
def program_edit(item_id):
    data = {
        "name": request.form.get("name", "").strip(),
        "category": request.form.get("category", "기타"),
        "program_date": request.form.get("date", "").strip(),
        "program_time": request.form.get("time", "").strip(),
        "place": request.form.get("place", "").strip(),
        "description": request.form.get("description", "").strip(),
        "icon": request.form.get("icon", "🎫").strip() or "🎫",
    }
    try:
        write_db().table("programs").update(data).eq("id", item_id).execute()
        flash("프로그램이 수정되었습니다.", "success")
    except Exception as e:
        flash(friendly(e), "error")
    return redirect(url_for("programs"))

@app.route("/programs/<item_id>/delete", methods=["POST"])
@admin_required
def program_delete(item_id):
    try:
        write_db().table("programs").delete().eq("id", item_id).execute()
        flash("프로그램이 삭제되었습니다.", "success")
    except Exception as e:
        flash(friendly(e), "error")
    return redirect(url_for("programs"))

@app.route("/schedule")
def schedule():
    return render_template("schedule.html", grouped=fetch_schedule())

@app.route("/schedule/add", methods=["GET", "POST"])
@admin_required
def schedule_add():
    if request.method == "POST":
        data = {
            "day": request.form.get("day", "").strip(),
            "time": request.form.get("time", "").strip(),
            "program": request.form.get("program", "").strip(),
            "place": request.form.get("place", "").strip(),
        }
        if not data["day"] or not data["time"] or not data["program"]:
            flash("날짜, 시간, 프로그램은 필수입니다.", "error")
        else:
            try:
                write_db().table("schedule").insert(data).execute()
                flash("시간표가 등록되었습니다.", "success")
                return redirect(url_for("schedule"))
            except Exception as e:
                flash(friendly(e), "error")
    return render_template("schedule_form.html", item=None)

@app.route("/schedule/<item_id>/edit", methods=["POST"])
@admin_required
def schedule_edit(item_id):
    data = {
        "day": request.form.get("day", "").strip(),
        "time": request.form.get("time", "").strip(),
        "program": request.form.get("program", "").strip(),
        "place": request.form.get("place", "").strip(),
    }
    try:
        write_db().table("schedule").update(data).eq("id", item_id).execute()
        flash("시간표가 수정되었습니다.", "success")
    except Exception as e:
        flash(friendly(e), "error")
    return redirect(url_for("schedule"))

@app.route("/schedule/<item_id>/delete", methods=["POST"])
@admin_required
def schedule_delete(item_id):
    try:
        write_db().table("schedule").delete().eq("id", item_id).execute()
        flash("시간표가 삭제되었습니다.", "success")
    except Exception as e:
        flash(friendly(e), "error")
    return redirect(url_for("schedule"))

@app.route("/booths")
def booths():
    cat = request.args.get("category", "전체")
    keyword = request.args.get("q", "").strip().lower()
    all_booths = fetch_booths()
    filtered = all_booths
    if cat != "전체":
        filtered = [b for b in filtered if b["category"] == cat]
    if keyword:
        filtered = [b for b in filtered if keyword in b["name"].lower()]
    categories = sorted({b["category"] for b in all_booths if b["category"]})
    return render_template("booths.html", booths=filtered, categories=categories, category=cat, keyword=keyword)

@app.route("/booths/add", methods=["GET", "POST"])
@admin_required
def booth_add():
    if request.method == "POST":
        image = request.files.get("image")
        image_uri = None
        if image and image.filename:
            raw = image.read()
            mime = image.mimetype or "image/jpeg"
            image_uri = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
        data = {
            "name": request.form.get("name", "").strip(),
            "category": request.form.get("category", "").strip(),
            "place": request.form.get("place", "").strip(),
            "hours": request.form.get("hours", "").strip(),
            "description": request.form.get("description", "").strip(),
            "icon": request.form.get("icon", "🏪").strip() or "🏪",
            "image": image_uri,
        }
        if not data["name"]:
            flash("부스 이름을 입력해주세요.", "error")
        else:
            try:
                write_db().table("booths").insert(data).execute()
                flash("부스가 등록되었습니다.", "success")
                return redirect(url_for("booths"))
            except Exception as e:
                flash(friendly(e), "error")
    return render_template("booth_form.html", item=None)

@app.route("/booths/<item_id>/edit", methods=["POST"])
@admin_required
def booth_edit(item_id):
    data = {
        "name": request.form.get("name", "").strip(),
        "category": request.form.get("category", "").strip(),
        "place": request.form.get("place", "").strip(),
        "hours": request.form.get("hours", "").strip(),
        "description": request.form.get("description", "").strip(),
        "icon": request.form.get("icon", "🏪").strip() or "🏪",
    }
    image = request.files.get("image")
    if image and image.filename:
        raw = image.read()
        mime = image.mimetype or "image/jpeg"
        data["image"] = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
    elif request.form.get("remove_image") == "1":
        data["image"] = None
    try:
        write_db().table("booths").update(data).eq("id", item_id).execute()
        flash("부스가 수정되었습니다.", "success")
    except Exception as e:
        flash(friendly(e), "error")
    return redirect(url_for("booths"))

@app.route("/booths/<item_id>/delete", methods=["POST"])
@admin_required
def booth_delete(item_id):
    try:
        write_db().table("booths").delete().eq("id", item_id).execute()
        flash("부스가 삭제되었습니다.", "success")
    except Exception as e:
        flash(friendly(e), "error")
    return redirect(url_for("booths"))

@app.route("/notices")
def notices():
    return render_template("notices.html", notices=fetch_notices())

@app.route("/notices/add", methods=["GET", "POST"])
@admin_required
def notice_add():
    if request.method == "POST":
        data = {
            "title": request.form.get("title", "").strip(),
            "content": request.form.get("content", "").strip(),
            "is_new": request.form.get("is_new") == "1",
        }
        if not data["title"]:
            flash("제목을 입력해주세요.", "error")
        else:
            try:
                write_db().table("notices").insert(data).execute()
                flash("공지사항이 등록되었습니다.", "success")
                return redirect(url_for("notices"))
            except Exception as e:
                flash(friendly(e), "error")
    return render_template("notice_form.html")

@app.route("/notices/<item_id>/edit", methods=["POST"])
@admin_required
def notice_edit(item_id):
    data = {
        "title": request.form.get("title", "").strip(),
        "content": request.form.get("content", "").strip(),
        "is_new": request.form.get("is_new") == "1",
    }
    try:
        write_db().table("notices").update(data).eq("id", item_id).execute()
        flash("공지사항이 수정되었습니다.", "success")
    except Exception as e:
        flash(friendly(e), "error")
    return redirect(url_for("notices"))

@app.route("/notices/<item_id>/delete", methods=["POST"])
@admin_required
def notice_delete(item_id):
    try:
        write_db().table("notices").delete().eq("id", item_id).execute()
        flash("공지사항이 삭제되었습니다.", "success")
    except Exception as e:
        flash(friendly(e), "error")
    return redirect(url_for("notices"))

@app.route("/directions")
def directions():
    return render_template("directions.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        kind = request.form.get("kind", "student")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        try:
            if kind == "student":
                res = db().table("profiles").select("*").eq("student_no", username).execute()
                profile = res.data[0] if res.data else None
                if not profile or not profile.get("school_email"):
                    flash("등록되지 않은 학번입니다.", "error")
                    return render_template("login.html")
                auth = sb.auth.sign_in_with_password({"email": profile["school_email"], "password": password})
            else:
                profile_res = db().table("profiles").select("*").eq("staff_username", username).execute()
                profile = profile_res.data[0] if profile_res.data else None
                if not profile:
                    flash("등록되지 않은 아이디입니다.", "error")
                    return render_template("login.html")
                fake_email = f"{username.lower()}@staff.local"
                auth = sb.auth.sign_in_with_password({"email": fake_email, "password": password})
            if auth.user:
                login_user(auth.user.id)
                flash("로그인되었습니다.", "success")
                return redirect(url_for("mypage"))
        except Exception:
            flash("아이디/학번 또는 비밀번호가 올바르지 않습니다.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    try:
        if sb:
            sb.auth.sign_out()
    except Exception:
        pass
    logout_user()
    return redirect(url_for("home"))

@app.route("/mypage")
def mypage():
    user = current_user()
    if not user:
        flash("로그인이 필요합니다.", "error")
        return redirect(url_for("login"))
    return render_template("mypage.html", user=user)

@app.route("/admin")
@admin_required
def admin():
    try:
        users = db().table("profiles").select("id,name,identity,is_admin,student_no,staff_code,staff_username").execute().data or []
    except Exception:
        users = []
    try:
        codes = db().table("staff_codes").select("*").execute().data or []
    except Exception:
        codes = []
    try:
        total = db().table("visits").select("id", count="exact").execute().count or 0
    except Exception:
        total = 0
    return render_template("admin.html", users=users, codes=codes, total=total)

@app.route("/admin/users/<uid>/role", methods=["POST"])
@admin_required
def role_change(uid):
    value = request.form.get("is_admin") == "1"
    try:
        write_db().table("profiles").update({"is_admin": value}).eq("id", uid).execute()
        flash("관리자 권한을 변경했습니다.", "success")
    except Exception as e:
        flash(friendly(e), "error")
    return redirect(url_for("admin"))

@app.route("/admin/staff-codes/add", methods=["POST"])
@admin_required
def staff_code_add():
    name = request.form.get("name", "").strip()
    if not name:
        flash("담당 선생님 이름을 입력해주세요.", "error")
        return redirect(url_for("admin"))
    code = "BK26-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    try:
        write_db().table("staff_codes").insert({"code": code, "name": name, "active": True}).execute()
        flash(f"새 인증코드: {code}", "success")
    except Exception as e:
        flash(friendly(e), "error")
    return redirect(url_for("admin"))

@app.route("/admin/staff-codes/<code>/disable", methods=["POST"])
@admin_required
def staff_code_disable(code):
    try:
        write_db().table("staff_codes").update({"active": False}).eq("code", code).execute()
        flash("인증코드를 비활성화했습니다.", "success")
    except Exception as e:
        flash(friendly(e), "error")
    return redirect(url_for("admin"))

@app.route("/schedule/download")
def schedule_download():
    grouped = fetch_schedule()
    lines = []
    for day, items in grouped.items():
        lines.append(f"[{day}]")
        for item in items:
            lines.append(f"{item.get('time','')}  {item.get('program','')}  ({item.get('place','')})")
        lines.append("")
    data = "\n".join(lines).encode("utf-8-sig")
    return send_file(BytesIO(data), as_attachment=True,
                     download_name="북악제_시간표.txt", mimetype="text/plain")

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
