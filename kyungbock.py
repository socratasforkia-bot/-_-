# -*- coding: utf-8 -*-
"""
경복고등학교 북악제 축제 홈페이지 (Supabase 로그인 연동판)
Streamlit 기반 반응형 웹앱

로그인 방식
    - 학생: 학번+이름 → (최초 1회) 학교이메일로 인증코드(OTP) 발송/확인 → 비밀번호 생성
            → 이후에는 학번+비밀번호로 로그인 (내부적으로 저장된 학교이메일로 인증)
    - 교직원: 인증코드 → (최초 1회) 코드에 사전 등록된 이름 확인 + 아이디/비밀번호 생성
            → 이후에는 아이디+비밀번호로 로그인
            (교직원은 실제 이메일이 없으므로 "아이디 + 가짜 이메일"로 Supabase Auth 계정을 만듭니다)

사전 준비 (필수)
    1) Supabase 프로젝트 SQL Editor에서 supabase_setup.sql 실행
    2) Supabase 대시보드 > Authentication > Providers > Email 에서
       "Confirm email"(이메일 인증) 을 반드시 OFF 로 설정
       (교직원 가짜 이메일은 인증 메일을 받을 수 없기 때문입니다)
    3) Supabase 대시보드 > Authentication > Email Templates > Magic Link
       템플릿 본문에 {{ .Token }} 을 추가해야 학생에게 6자리 인증코드가 발송됩니다
       (기본 템플릿은 클릭형 링크만 있습니다)
    4) .streamlit/secrets.toml 에 아래 값 채우기
        SUPABASE_URL = "https://xxxx.supabase.co"
        SUPABASE_ANON_KEY = "..."
        SUPABASE_SERVICE_KEY = "..."   # 관리자 기능(권한부여, 인증코드 발급 등)에 필요, 선택
        COOKIE_PASSWORD = "아무 긴 임의 문자열"  # 로그인 유지용 쿠키 암호화 키 (필수 권장)

실행:
    pip install streamlit supabase streamlit-cookies-manager
    streamlit run app.py

----------------------------------------------------------------------
[수정 사항 3 - 관리자가 공지사항을 수정/삭제하지 못하던 문제 해결]
기존 코드의 "사이트 관리" 탭에는 공지사항을 새로 "등록"하는 폼만 있고,
이미 등록된 공지사항을 수정하거나 삭제하는 기능은 아예 없었습니다.

해결: page_admin() 의 "사이트 관리" 탭에 "공지사항 관리" 섹션을 추가했습니다.
----------------------------------------------------------------------

[수정 사항 4 - 공지사항 / 부스 정보가 메인 화면에 반영되지 않던 문제 해결]
공지사항(notices)과 부스(booths)를 Supabase 테이블로 옮기고, 페이지를 그릴 때마다
fetch_notices() / fetch_booths() 로 DB에서 직접 읽어오도록 바꿨습니다.

DB 준비: 아래 SQL을 Supabase SQL Editor에서 한 번 실행해주세요.

    create table if not exists notices (
        id uuid primary key default gen_random_uuid(),
        title text not null,
        content text,
        is_new boolean not null default true,
        created_at timestamptz not null default now()
    );
    alter table notices enable row level security;
    create policy "notices are viewable by everyone"
        on notices for select
        using (true);

    create table if not exists booths (
        id uuid primary key default gen_random_uuid(),
        name text not null,
        category text,
        place text,
        hours text,
        description text,
        icon text,
        image text,
        created_at timestamptz not null default now()
    );
    alter table booths enable row level security;
    create policy "booths are viewable by everyone"
        on booths for select
        using (true);
----------------------------------------------------------------------

[수정 사항 5 - 사이드바(드로어)에서 '메인' 항목 제거 + 헤더 클릭 시 메인 이동]
드로어 메뉴에서는 '메인' 항목을 뺐습니다. 로고 클릭으로 메인 이동이 가능합니다.
----------------------------------------------------------------------

[수정 사항 6 - 교직원 로그인 방식 변경: 코드에 사전 등록된 이름 + 아이디/비밀번호]
관리자가 인증코드를 발급할 때 담당 선생님 "이름"도 함께 입력합니다(staff_codes.name).
선생님은 최초 등록 시 코드 확인 후 "아이디(로그인 ID)"와 "비밀번호"를 새로 만듭니다.
이후 로그인은 "아이디+비밀번호"로 합니다.

DB 준비 (추가 SQL):
    alter table staff_codes add column if not exists name text;
    alter table profiles add column if not exists staff_username text unique;
----------------------------------------------------------------------

[수정 사항 7 - 부스 사진 + 아이콘 함께 표시]
사진이 있어도 아이콘이 사진 위 모서리에 작은 배지 형태로 함께 보이도록 했습니다.
----------------------------------------------------------------------

[수정 사항 8 - 공지사항/부스 목록 캐싱으로 체감 속도 개선 + DB 요청 절감]
fetch_notices()/fetch_booths()에 @st.cache_data(ttl=...)를 적용했습니다.
----------------------------------------------------------------------

[수정 사항 9 - (제거됨) 방명록 기능]
이전 버전에는 방명록(guestbook) 페이지가 있었으나, 요청에 따라 완전히 제거했습니다.
(테이블/함수/메뉴 항목을 모두 삭제했습니다. 기존에 guestbook 테이블을 만들어두셨다면
 더 이상 이 앱에서 사용하지 않으니 필요 없다면 Supabase에서 직접 삭제하셔도 됩니다.)
----------------------------------------------------------------------

[수정 사항 10 - 관리자 방문자 통계]
방문자가 사이트에 처음 접속(세션당 1회)하면 조용히 방문 기록을 1건 남기고, 관리자
페이지에서 누적 방문자 수와 최근 14일 일별 방문자 추이를 확인할 수 있습니다.
개인을 특정할 수 있는 정보(IP, 쿠키 등)는 저장하지 않고 방문 시각만 기록합니다.

DB 준비 (Supabase SQL Editor에서 한 번 실행):

    create table if not exists visits (
        id uuid primary key default gen_random_uuid(),
        created_at timestamptz not null default now()
    );
    alter table visits enable row level security;
    create policy "visits are insertable by everyone"
        on visits for insert with check (true);
    create policy "visits are viewable by everyone"
        on visits for select using (true);
----------------------------------------------------------------------

[수정 사항 11 - 프로그램/시간표를 관리자가 추가·수정·삭제 가능하도록 변경 +
                사이드바 전용 "프로그램 구성" 메뉴 추가]
기존에는 프로그램(programs)과 시간표(schedule)가 st.session_state에만 저장되는
데모용 인메모리 데이터였습니다. 그래서 관리자가 수정할 방법이 없었고, 서버가
재시작되면 초기화되었습니다.

해결:
    1) 프로그램(programs)과 시간표(schedule)를 각각 Supabase 테이블로 옮기고,
       fetch_programs() / fetch_schedule_by_day() 로 항상 DB에서 최신 데이터를
       읽어오도록 했습니다.
    2) "프로그램" 페이지, "시간표" 페이지 모두 공지사항/부스 정보 페이지와
       동일한 패턴으로 — 각 항목 아래에 관리자 전용 "수정/삭제" 폼을 열 수 있게
       하고, 화면 우측 하단 "+" 버튼으로 새 항목을 등록하는 전용 페이지
       (프로그램 등록 / 시간표 등록)로 이동하도록 만들었습니다.
    3) 요청하신 대로 "프로그램 구성" 메뉴를 새로 만들되, **사이드바(햄버거 메뉴)
       에만** 노출됩니다(메인 화면 상단 아이콘 메뉴에는 넣지 않았습니다). 이 메뉴는
       기존 "프로그램" 페이지로 그대로 연결되며, 그 페이지 안에서 관리자는 등록·
       수정·삭제를, 일반 방문자는 조회를 할 수 있습니다.

DB 준비 (Supabase SQL Editor에서 한 번 실행):

    create table if not exists programs (
        id uuid primary key default gen_random_uuid(),
        name text not null,
        category text,
        program_date text,
        program_time text,
        place text,
        description text,
        icon text,
        created_at timestamptz not null default now()
    );
    alter table programs enable row level security;
    create policy "programs are viewable by everyone"
        on programs for select using (true);

    create table if not exists schedule (
        id uuid primary key default gen_random_uuid(),
        day text not null,
        time text not null,
        program text not null,
        place text,
        created_at timestamptz not null default now()
    );
    alter table schedule enable row level security;
    create policy "schedule is viewable by everyone"
        on schedule for select using (true);

    (등록/수정/삭제는 SUPABASE_SERVICE_KEY로 RLS를 우회해 처리하므로
     별도의 insert/update/delete 정책은 필요 없습니다.)
----------------------------------------------------------------------
"""

import streamlit as st
import streamlit.components.v1 as components
import base64
import io
from datetime import datetime, date, time as dtime, timedelta
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

# ----------------------------------------------------------------------
# 학교 로고 (경복고등학교 엠블럼)
# ----------------------------------------------------------------------
LOGO_PNG_BASE64 = (
    "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"
)
LOGO_DATA_URI = f"data:image/png;base64,{LOGO_PNG_BASE64}"
try:
    LOGO_IMAGE = Image.open(io.BytesIO(base64.b64decode(LOGO_PNG_BASE64))) if Image else "🏫"
except Exception:
    LOGO_IMAGE = "🏫"

# ----------------------------------------------------------------------
# 기본 설정
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="경복고등학교 북악제",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed",
)

FESTIVAL_NAME = "북악제"
FESTIVAL_SLOGAN = "빛나는 우리, 하나의 이야기"
FESTIVAL_DATE = date(2026, 10, 30)
FESTIVAL_DATETIME = datetime.combine(FESTIVAL_DATE, dtime(0, 0, 0))
FESTIVAL_TZ_OFFSET = "+09:00"

FAKE_EMAIL_DOMAIN = "bukakje.internal"

NOTICES_CACHE_TTL = 20
BOOTHS_CACHE_TTL = 30
PROGRAMS_CACHE_TTL = 30
SCHEDULE_CACHE_TTL = 30

# ----------------------------------------------------------------------
# Supabase 클라이언트
# ----------------------------------------------------------------------
try:
    from supabase import create_client, Client
except ImportError:
    st.error(
        "`supabase` 패키지가 설치되어 있지 않습니다.\n\n"
        "터미널에서 `pip install supabase` 를 실행한 뒤 다시 시작해주세요."
    )
    st.stop()

try:
    from streamlit_cookies_manager import EncryptedCookieManager
except ImportError:
    st.error(
        "`streamlit-cookies-manager` 패키지가 설치되어 있지 않습니다.\n\n"
        "터미널에서 `pip install streamlit-cookies-manager` 를 실행한 뒤 다시 시작해주세요."
    )
    st.stop()


def _debug_secret_paths() -> str:
    candidates = []
    try:
        candidates.append(Path(__file__).resolve().parent / ".streamlit" / "secrets.toml")
    except Exception:
        pass
    candidates.append(Path.home() / ".streamlit" / "secrets.toml")

    lines = []
    for p in candidates:
        if p.exists():
            lines.append(f"- `{p}` → 존재함 ✅")
        else:
            parent = p.parent
            if parent.exists():
                found = [f.name for f in parent.iterdir()]
                hint = f" (이 폴더 안 실제 파일들: {found})" if found else " (이 폴더는 비어있음)"
            else:
                hint = " (이 폴더 자체가 없음)"
            lines.append(f"- `{p}` → 없음 ❌{hint}")
    return "\n".join(lines)


def _get_secret(key: str, required: bool = True, default=None):
    try:
        val = st.secrets.get(key)
    except Exception:
        val = None
        if required:
            st.error(
                "`secrets.toml` 파일을 찾을 수 없습니다.\n\n"
                "다음 경로들을 확인해봤습니다.\n\n"
                f"{_debug_secret_paths()}\n\n"
                "파일이 아예 없다면 스크립트가 있는 폴더 밑에 `.streamlit` 폴더를 만들고 "
                "그 안에 `secrets.toml` 파일을 아래 형식으로 만들어주세요.\n\n"
                "```\n"
                "SUPABASE_URL = \"https://xxxxxxxxxxxx.supabase.co\"\n"
                "SUPABASE_ANON_KEY = \"anon 키\"\n"
                "SUPABASE_SERVICE_KEY = \"service_role 키 (선택)\"\n"
                "```"
            )
            st.stop()
    if required and not val:
        st.error(
            f"`.streamlit/secrets.toml` 에 `{key}` 값이 설정되어 있지 않습니다.\n\n"
            "함께 받은 `supabase_setup.sql` 안내와 secrets.toml 예시를 참고해 설정해주세요."
        )
        st.stop()
    if not val:
        return default
    return val


SUPABASE_URL = _get_secret("SUPABASE_URL")
SUPABASE_ANON_KEY = _get_secret("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = _get_secret("SUPABASE_SERVICE_KEY", required=False)

COOKIE_PASSWORD = _get_secret(
    "COOKIE_PASSWORD", required=False,
    default="bukakje-insecure-default-change-me-in-secrets-toml",
)
if COOKIE_PASSWORD == "bukakje-insecure-default-change-me-in-secrets-toml":
    st.warning(
        "⚠️ `secrets.toml` 에 `COOKIE_PASSWORD` 가 설정되어 있지 않아 "
        "임시 기본값을 사용합니다. 서버를 재시작하면 로그인 유지 쿠키가 무효화될 수 있으니 "
        "`COOKIE_PASSWORD = \"아무 긴 임의 문자열\"` 을 secrets.toml에 추가해주세요.",
        icon="⚠️",
    )


def get_user_client() -> "Client":
    if "sb_client" not in st.session_state:
        st.session_state.sb_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return st.session_state.sb_client


@st.cache_resource
def get_admin_client():
    if not SUPABASE_SERVICE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def student_email(student_no: str) -> str:
    return f"student-{student_no.strip()}@{FAKE_EMAIL_DOMAIN}"


def staff_login_email(username: str) -> str:
    return f"staffid-{username.strip()}@{FAKE_EMAIL_DOMAIN}"


# ----------------------------------------------------------------------
# 쿠키 매니저 초기화 (로그인 유지용)
# ----------------------------------------------------------------------
cookies = EncryptedCookieManager(prefix="bukakje_", password=COOKIE_PASSWORD)
if not cookies.ready():
    st.stop()


def save_auth_cookies(session):
    if session is None:
        return
    try:
        cookies["sb_access_token"] = session.access_token or ""
        cookies["sb_refresh_token"] = session.refresh_token or ""
        cookies.save()
    except Exception:
        pass


def clear_auth_cookies():
    try:
        cookies["sb_access_token"] = ""
        cookies["sb_refresh_token"] = ""
        cookies.save()
    except Exception:
        pass


def try_restore_session_from_cookies():
    if st.session_state.get("current_user_id"):
        return

    access_token = cookies.get("sb_access_token")
    refresh_token = cookies.get("sb_refresh_token")
    if not access_token or not refresh_token:
        return

    client = get_user_client()
    try:
        client.auth.set_session(access_token, refresh_token)
        user_res = client.auth.get_user()
    except Exception:
        clear_auth_cookies()
        return

    if user_res and user_res.user:
        st.session_state.current_user_id = user_res.user.id
        st.session_state.profile_cache = None
    else:
        clear_auth_cookies()


# ----------------------------------------------------------------------
# 디자인 토큰
# ----------------------------------------------------------------------
NAVY = "#0F1F3D"
NAVY_2 = "#16294F"
ORANGE = "#F2994A"
ORANGE_DARK = "#E07B2E"
BLUE_PILL = "#2F5D9F"
GREEN = "#2E9E5B"
BG = "#F5F6FA"
CARD = "#FFFFFF"
TEXT = "#1F2937"
MUTED = "#6B7280"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');

html, body, [class*="css"]  {{
    font-family: 'Noto Sans KR', sans-serif;
}}
.stApp {{
    background: {BG};
}}
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
header[data-testid="stHeader"] {{display: none;}}

.block-container {{
    padding-top: 4.4rem !important;
    padding-bottom: 2rem;
}}

.bk-drawer-checkbox {{
    display: none;
}}

.bk-topbar {{
    position: fixed;
    top: 0; left: 0; right: 0;
    height: 3.4rem;
    background: {NAVY};
    color: white;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 18px;
    z-index: 1000000;
    box-shadow: 0 2px 10px rgba(0,0,0,0.15);
}}
.bk-brand {{
    font-weight: 900;
    font-size: 17px;
    color: white !important;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.bk-brand-logo {{
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: white;
    object-fit: contain;
    padding: 2px;
}}
.bk-brand:hover {{
    color: {ORANGE} !important;
}}
.bk-hamburger {{
    cursor: pointer;
    font-size: 24px;
    line-height: 1;
    background: {ORANGE};
    color: white;
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    user-select: none;
}}

.bk-backdrop {{
    position: fixed;
    inset: 0;
    background: rgba(10,15,30,0.55);
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.25s ease;
    z-index: 1000001;
    display: block;
    cursor: pointer;
}}

.bk-drawer {{
    position: fixed;
    top: 0; right: 0;
    height: 100vh;
    width: min(300px, 82vw);
    background: {NAVY};
    transform: translateX(100%);
    transition: transform 0.3s ease;
    z-index: 1000002;
    padding: 18px 16px;
    overflow-y: auto;
    box-shadow: -8px 0 24px rgba(0,0,0,0.3);
}}
.bk-drawer-head {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    color: white;
    font-weight: 900;
    font-size: 16px;
    margin-bottom: 14px;
}}
.bk-drawer-close {{
    cursor: pointer;
    font-size: 18px;
    color: white;
    background: rgba(255,255,255,0.12);
    width: 32px; height: 32px;
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
}}
.bk-drawer-link {{
    display: block;
    color: #EDEFF5 !important;
    text-decoration: none !important;
    font-weight: 600;
    font-size: 15px;
    padding: 12px 10px;
    border-radius: 10px;
    margin-bottom: 4px;
}}
.bk-drawer-link:hover {{
    background: rgba(255,255,255,0.10);
    color: {ORANGE} !important;
}}
.bk-drawer-link.bk-active {{
    background: {ORANGE};
    color: white !important;
}}
.bk-drawer-divider {{
    border: none;
    border-top: 1px solid rgba(255,255,255,0.15);
    margin: 12px 0;
}}
.bk-drawer-user {{
    color: #C9D2E8;
    font-size: 13px;
    padding: 0 10px 8px 10px;
}}

.bk-drawer-checkbox:checked ~ .bk-backdrop {{
    opacity: 1;
    pointer-events: auto;
}}
.bk-drawer-checkbox:checked ~ .bk-drawer {{
    transform: translateX(0);
}}

.bk-card {{
    background: {CARD};
    border-radius: 16px;
    padding: 22px;
    box-shadow: 0 2px 14px rgba(15,31,61,0.08);
    height: 100%;
}}
.bk-card h4 {{
    margin: 0 0 12px 0;
    color: {NAVY};
}}
.bk-badge-new {{
    background: {ORANGE};
    color: white;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 20px;
    margin-left: 8px;
}}
.bk-pill {{
    display: inline-block;
    background: {NAVY};
    color: white;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
}}
.bk-chip {{
    display: inline-block;
    background: #EEF1F8;
    color: {NAVY};
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    margin-right: 6px;
}}

.bk-card-btn {{
    display: inline-block;
    margin-top: 10px;
    color: {ORANGE_DARK} !important;
    font-weight: 700;
    font-size: 14px;
    text-decoration: none !important;
}}
.bk-card-btn:hover {{
    text-decoration: underline !important;
}}

.bk-hero {{
    position: relative;
    border-radius: 20px;
    padding: 46px 40px;
    min-height: 300px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    justify-content: center;
    background:
      radial-gradient(circle at 10% 20%, rgba(242,153,74,0.55) 0px, transparent 3px),
      radial-gradient(circle at 25% 15%, rgba(242,153,74,0.55) 0px, transparent 3px),
      radial-gradient(circle at 40% 25%, rgba(242,153,74,0.55) 0px, transparent 3px),
      radial-gradient(circle at 55% 12%, rgba(242,153,74,0.55) 0px, transparent 3px),
      radial-gradient(circle at 70% 22%, rgba(242,153,74,0.55) 0px, transparent 3px),
      radial-gradient(circle at 85% 15%, rgba(242,153,74,0.55) 0px, transparent 3px),
      radial-gradient(circle at 95% 25%, rgba(242,153,74,0.55) 0px, transparent 3px),
      linear-gradient(180deg, {NAVY} 0%, {NAVY_2} 60%, #0B1730 100%);
    color: white;
    overflow: hidden;
}}
.bk-hero .eyebrow {{
    font-size: 13px;
    color: #C9D2E8;
    font-weight: 600;
    letter-spacing: 1px;
}}
.bk-hero h1 {{
    font-size: 64px;
    font-weight: 900;
    margin: 4px 0 6px 0;
    line-height: 1.05;
    color: white !important;
}}
.bk-hero .slogan {{
    font-size: 18px;
    color: #E7EBF6;
    margin-bottom: 18px;
}}
.bk-hero .meta {{
    font-size: 14px;
    color: #D8DEEE;
}}
.bk-dday-box {{
    background: white;
    border-radius: 16px;
    padding: 18px 22px;
    text-align: center;
    color: {NAVY};
    box-shadow: 0 8px 24px rgba(0,0,0,0.25);
}}
.bk-dday-box .num {{
    font-size: 36px;
    font-weight: 900;
    color: {ORANGE_DARK};
}}

.bk-iconmenu .stButton>button {{
    width: 100%;
    border: none;
    background: white;
    border-radius: 14px;
    padding: 16px 4px;
    box-shadow: 0 2px 10px rgba(15,31,61,0.07);
    font-weight: 700;
    color: {NAVY};
}}
.bk-iconmenu .stButton>button:hover {{
    background: #EEF1F8;
    color: {ORANGE_DARK};
}}

div.stButton>button {{
    border-radius: 10px;
}}

.bk-section-title {{
    font-size: 22px;
    font-weight: 900;
    color: {NAVY};
    margin: 30px 0 14px 0;
}}
.bk-footer {{
    margin-top: 40px;
    padding: 24px;
    background: {NAVY};
    color: #D8DEEE;
    border-radius: 16px;
    font-size: 14px;
}}
hr {{border-color: #E5E7EF;}}

.bk-fab {{
    position: fixed;
    right: 22px;
    bottom: 22px;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: {ORANGE};
    color: white !important;
    font-size: 30px;
    font-weight: 900;
    line-height: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    text-decoration: none !important;
    box-shadow: 0 6px 18px rgba(224,123,46,0.45);
    z-index: 999998;
}}
.bk-fab:hover {{
    background: {ORANGE_DARK};
}}

.bk-media-wrap {{
    position: relative;
    width: 100%;
}}
.bk-media-icon-badge {{
    position: absolute;
    right: 8px;
    bottom: 8px;
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background: white;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------------------------------------------------
# 세션 상태 초기화
#  - 프로그램(programs)/시간표(schedule)는 이제 Supabase 테이블로 관리하므로
#    더 이상 세션 상태에 기본값을 넣지 않습니다.
# ----------------------------------------------------------------------
def init_state():
    ss = st.session_state

    if "page" not in ss:
        ss.page = "메인"

    if "current_user_id" not in ss:
        ss.current_user_id = None

    if "profile_cache" not in ss:
        ss.profile_cache = None

    if "student_step" not in ss:
        ss.student_step = "check"
    if "staff_step" not in ss:
        ss.staff_step = "check"

    if "site_info" not in ss:
        ss.site_info = {
            "address": "서울특별시 종로구 자하문로 17길 33 (경복고등학교)",
            "subway": "3호선 경복궁역 3번 출구 도보 15분",
            "bus": "간선/지선버스 다수 노선 '경복고등학교' 정류장 하차",
            "walk": "경복궁역에서 도보 약 15분",
            "phone": "02-123-4567 (행사 운영본부)",
            "email": "bukakje@kboye.kr",
            "hours": "평일 09:00 ~ 17:00",
        }


init_state()
ss = st.session_state

try_restore_session_from_cookies()


# ----------------------------------------------------------------------
# 헬퍼
# ----------------------------------------------------------------------
def go(page_name: str):
    ss.page = page_name


def reset_login_steps():
    ss.student_step = "check"
    ss.staff_step = "check"
    for k in ("pending_student_no", "pending_student_name", "pending_student_email",
              "pending_staff_code", "pending_staff_name"):
        ss.pop(k, None)


def current_user():
    ss.last_profile_error = None
    uid = ss.get("current_user_id")
    if not uid:
        return None
    cache = ss.get("profile_cache")
    if cache and cache.get("id") == uid:
        return cache
    try:
        client = get_user_client()
        res = client.table("profiles").select("*").eq("id", uid).execute()
    except Exception as e:
        ss.last_profile_error = f"프로필 조회 중 오류: {e}"
        return None
    if res.data:
        ss.profile_cache = res.data[0]
        return ss.profile_cache
    ss.last_profile_error = (
        "로그인 세션은 있지만 profiles 테이블에서 해당 사용자 행을 찾지 못했습니다. "
        "(회원가입 시 프로필 insert가 실패했거나, RLS 정책이 select를 막고 있을 수 있습니다.)"
    )
    return None


def is_admin():
    u = current_user()
    return bool(u and u.get("is_admin"))


# ----------------------------------------------------------------------
# DB 오류 처리 헬퍼
# ----------------------------------------------------------------------
def _friendly_db_error(e: Exception) -> str:
    msg = str(e)
    if "infinite recursion detected in policy" in msg or "42P17" in msg:
        return (
            "Supabase의 RLS(행 수준 보안) 정책이 자기 자신을 참조해서 "
            "무한 재귀에 빠졌습니다 (42P17). Supabase 대시보드 SQL Editor에서 "
            "제공받은 RLS 수정 스크립트를 실행한 뒤 다시 시도해주세요."
        )
    if "relation" in msg and "does not exist" in msg:
        return (
            "필요한 테이블이 아직 없습니다. 이 파일 상단 주석의 SQL을 "
            "Supabase SQL Editor에서 먼저 실행해주세요.\n\n"
            f"(원본 오류: {msg})"
        )
    return f"데이터베이스 오류가 발생했습니다: {msg}"


def _write_client():
    admin_client = get_admin_client()
    return admin_client if admin_client is not None else get_user_client()


# ----------------------------------------------------------------------
# 공지사항 / 부스 — Supabase 연동
# ----------------------------------------------------------------------
@st.cache_data(ttl=NOTICES_CACHE_TTL)
def fetch_notices():
    client = get_user_client()
    try:
        res = client.table("notices").select("*").order("created_at", desc=True).execute()
    except Exception as e:
        st.error(_friendly_db_error(e))
        return []
    result = []
    for row in (res.data or []):
        created = row.get("created_at") or ""
        result.append({
            "id": row["id"],
            "title": row.get("title") or "",
            "content": row.get("content") or "",
            "date": created[:10] if created else "",
            "new": bool(row.get("is_new")),
        })
    return result


def add_notice(title: str, content: str, is_new: bool):
    try:
        _write_client().table("notices").insert(
            {"title": title, "content": content, "is_new": is_new}
        ).execute()
        fetch_notices.clear()
        return True, "공지사항이 등록되었습니다."
    except Exception as e:
        return False, _friendly_db_error(e)


def update_notice(notice_id, title: str, content: str, is_new: bool):
    try:
        _write_client().table("notices").update(
            {"title": title, "content": content, "is_new": is_new}
        ).eq("id", notice_id).execute()
        fetch_notices.clear()
        return True, "공지사항이 수정되었습니다."
    except Exception as e:
        return False, _friendly_db_error(e)


def delete_notice(notice_id):
    try:
        _write_client().table("notices").delete().eq("id", notice_id).execute()
        fetch_notices.clear()
        return True, "공지사항이 삭제되었습니다."
    except Exception as e:
        return False, _friendly_db_error(e)


@st.cache_data(ttl=BOOTHS_CACHE_TTL)
def fetch_booths():
    client = get_user_client()
    try:
        res = client.table("booths").select("*").order("created_at", desc=True).execute()
    except Exception as e:
        st.error(_friendly_db_error(e))
        return []
    result = []
    for row in (res.data or []):
        result.append({
            "id": row["id"],
            "name": row.get("name") or "",
            "category": row.get("category") or "",
            "place": row.get("place") or "",
            "hours": row.get("hours") or "",
            "desc": row.get("description") or "",
            "icon": row.get("icon") or "🏪",
            "image": row.get("image"),
        })
    return result


def add_booth(data: dict):
    try:
        _write_client().table("booths").insert({
            "name": data["name"], "category": data["category"], "place": data["place"],
            "hours": data["hours"], "description": data["desc"], "icon": data["icon"],
            "image": data.get("image"),
        }).execute()
        fetch_booths.clear()
        return True, "부스가 등록되었습니다."
    except Exception as e:
        return False, _friendly_db_error(e)


def update_booth(booth_id, data: dict):
    payload = {
        "name": data["name"], "category": data["category"], "place": data["place"],
        "hours": data["hours"], "description": data["desc"], "icon": data["icon"],
    }
    if "image" in data:
        payload["image"] = data["image"]
    try:
        _write_client().table("booths").update(payload).eq("id", booth_id).execute()
        fetch_booths.clear()
        return True, "부스 정보가 수정되었습니다."
    except Exception as e:
        return False, _friendly_db_error(e)


def delete_booth(booth_id):
    try:
        _write_client().table("booths").delete().eq("id", booth_id).execute()
        fetch_booths.clear()
        return True, "부스가 삭제되었습니다."
    except Exception as e:
        return False, _friendly_db_error(e)


# ----------------------------------------------------------------------
# 프로그램 — Supabase 연동 (관리자 추가/수정/삭제 가능)
# ----------------------------------------------------------------------
@st.cache_data(ttl=PROGRAMS_CACHE_TTL)
def fetch_programs():
    client = get_user_client()
    try:
        res = client.table("programs").select("*").order("created_at", desc=True).execute()
    except Exception as e:
        st.error(_friendly_db_error(e))
        return []
    result = []
    for row in (res.data or []):
        result.append({
            "id": row["id"],
            "name": row.get("name") or "",
            "category": row.get("category") or "기타",
            "date": row.get("program_date") or "",
            "time": row.get("program_time") or "",
            "place": row.get("place") or "",
            "desc": row.get("description") or "",
            "icon": row.get("icon") or "🎫",
        })
    return result


def add_program(data: dict):
    try:
        _write_client().table("programs").insert({
            "name": data["name"], "category": data["category"],
            "program_date": data["date"], "program_time": data["time"],
            "place": data["place"], "description": data["desc"],
            "icon": data["icon"],
        }).execute()
        fetch_programs.clear()
        return True, "프로그램이 등록되었습니다."
    except Exception as e:
        return False, _friendly_db_error(e)


def update_program(program_id, data: dict):
    try:
        _write_client().table("programs").update({
            "name": data["name"], "category": data["category"],
            "program_date": data["date"], "program_time": data["time"],
            "place": data["place"], "description": data["desc"],
            "icon": data["icon"],
        }).eq("id", program_id).execute()
        fetch_programs.clear()
        return True, "프로그램이 수정되었습니다."
    except Exception as e:
        return False, _friendly_db_error(e)


def delete_program(program_id):
    try:
        _write_client().table("programs").delete().eq("id", program_id).execute()
        fetch_programs.clear()
        return True, "프로그램이 삭제되었습니다."
    except Exception as e:
        return False, _friendly_db_error(e)


# ----------------------------------------------------------------------
# 시간표 — Supabase 연동 (관리자 추가/수정/삭제 가능)
# ----------------------------------------------------------------------
@st.cache_data(ttl=SCHEDULE_CACHE_TTL)
def fetch_schedule_flat():
    client = get_user_client()
    try:
        res = client.table("schedule").select("*").order("day").order("time").execute()
    except Exception as e:
        st.error(_friendly_db_error(e))
        return []
    result = []
    for row in (res.data or []):
        result.append({
            "id": row["id"],
            "day": row.get("day") or "",
            "time": row.get("time") or "",
            "program": row.get("program") or "",
            "place": row.get("place") or "",
        })
    return result


def fetch_schedule_by_day():
    """일자별로 묶은 dict를 반환합니다. {day: [items...]} (day 기준 오름차순 정렬)"""
    grouped = {}
    for item in fetch_schedule_flat():
        grouped.setdefault(item["day"], []).append(item)
    return dict(sorted(grouped.items()))


def add_schedule_item(data: dict):
    try:
        _write_client().table("schedule").insert({
            "day": data["day"], "time": data["time"],
            "program": data["program"], "place": data["place"],
        }).execute()
        fetch_schedule_flat.clear()
        return True, "시간표 항목이 등록되었습니다."
    except Exception as e:
        return False, _friendly_db_error(e)


def update_schedule_item(item_id, data: dict):
    try:
        _write_client().table("schedule").update({
            "day": data["day"], "time": data["time"],
            "program": data["program"], "place": data["place"],
        }).eq("id", item_id).execute()
        fetch_schedule_flat.clear()
        return True, "시간표 항목이 수정되었습니다."
    except Exception as e:
        return False, _friendly_db_error(e)


def delete_schedule_item(item_id):
    try:
        _write_client().table("schedule").delete().eq("id", item_id).execute()
        fetch_schedule_flat.clear()
        return True, "시간표 항목이 삭제되었습니다."
    except Exception as e:
        return False, _friendly_db_error(e)


# ----------------------------------------------------------------------
# 방문자 통계 — Supabase 연동
# ----------------------------------------------------------------------
VISIT_STATS_CACHE_TTL = 60


def record_visit():
    if ss.get("visit_recorded"):
        return
    ss.visit_recorded = True
    try:
        get_user_client().table("visits").insert({}).execute()
    except Exception:
        pass


@st.cache_data(ttl=VISIT_STATS_CACHE_TTL)
def fetch_visit_total() -> int:
    client = get_user_client()
    try:
        res = client.table("visits").select("id", count="exact").execute()
        return res.count or 0
    except Exception:
        return 0


@st.cache_data(ttl=VISIT_STATS_CACHE_TTL)
def fetch_visit_daily(days: int = 14) -> dict:
    client = get_user_client()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")
    try:
        res = (
            client.table("visits")
            .select("created_at")
            .gte("created_at", since)
            .limit(20000)
            .execute()
        )
    except Exception:
        return {}
    counts = {}
    for row in (res.data or []):
        created = row.get("created_at") or ""
        day = created[:10]
        if day:
            counts[day] = counts.get(day, 0) + 1
    return dict(sorted(counts.items()))


# ----------------------------------------------------------------------
# 부스 카드에 쓸 이미지 / 아이콘 영역 HTML
# ----------------------------------------------------------------------
def booth_media_html(b: dict, height: str = "150px") -> str:
    icon = b.get("icon") or "🏪"
    if b.get("image"):
        return (
            f'<div class="bk-media-wrap" style="height:{height};margin-bottom:10px;">'
            f'<div style="width:100%;height:100%;border-radius:14px;overflow:hidden;'
            f'box-shadow:0 3px 12px rgba(15,31,61,0.15);">'
            f'<img src="{b["image"]}" style="width:100%;height:100%;object-fit:cover;'
            f'display:block;">'
            f'</div>'
            f'<div class="bk-media-icon-badge">{icon}</div>'
            f'</div>'
        )
    return (
        f'<div style="width:100%;height:{height};border-radius:14px;margin-bottom:10px;'
        f'background:linear-gradient(135deg,{NAVY} 0%, {BLUE_PILL} 100%);'
        f'display:flex;align-items:center;justify-content:center;font-size:42px;">'
        f'{icon}'
        f'</div>'
    )


def days_left():
    return (FESTIVAL_DATE - date.today()).days


def render_dday_box():
    target_iso = FESTIVAL_DATETIME.strftime("%Y-%m-%dT%H:%M:%S") + FESTIVAL_TZ_OFFSET
    components.html(
        f"""
        <div style="padding:20px 0;box-sizing:border-box;">
            <div style="font-family:'Noto Sans KR',sans-serif;background:white;border-radius:20px;
                        height:260px;box-sizing:border-box;
                        display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;
                        padding:24px 22px;text-align:center;color:{NAVY};
                        box-shadow:0 8px 24px rgba(0,0,0,0.25);">
                <div>
                    <div style="font-size:13px;font-weight:700;color:{MUTED};letter-spacing:2px;">D-DAY</div>
                    <div id="bk-dday-num" style="font-size:44px;font-weight:900;color:{ORANGE_DARK};
                                font-variant-numeric:tabular-nums;letter-spacing:1px;margin-top:4px;">-</div>
                    <div id="bk-dday-sub" style="font-size:13px;color:{TEXT};margin-top:4px;">계산 중...</div>
                </div>
                <span style="display:inline-block;background:{NAVY};color:white;padding:6px 16px;
                            border-radius:20px;font-size:13px;font-weight:600;">
                    📅 {FESTIVAL_DATE.strftime('%Y.%m.%d')}
                </span>
            </div>
        </div>
        <script>
            const target = new Date("{target_iso}").getTime();
            function bkTick() {{
                const now = new Date().getTime();
                const diff = target - now;
                const numEl = document.getElementById('bk-dday-num');
                const subEl = document.getElementById('bk-dday-sub');
                if (!numEl || !subEl) return;

                if (diff <= 0) {{
                    numEl.style.fontSize = '36px';
                    numEl.innerText = '0';
                    subEl.innerText = '축제가 시작되었습니다!';
                }} else if (diff < 86400000) {{
                    const h = Math.floor(diff / (1000 * 60 * 60));
                    const m = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                    const s = Math.floor((diff % (1000 * 60)) / 1000);
                    const pad = (n) => String(n).padStart(2, '0');
                    numEl.style.fontSize = '30px';
                    numEl.innerText = pad(h) + ':' + pad(m) + ':' + pad(s);
                    subEl.innerText = '곧 시작합니다!';
                }} else {{
                    const d = Math.ceil(diff / 86400000);
                    numEl.style.fontSize = '36px';
                    numEl.innerText = String(d);
                    subEl.innerText = d + '일 남았습니다!';
                }}
            }}
            bkTick();
            setInterval(bkTick, 1000);
        </script>
        """,
        height=300,
    )


# ---------- 학생 로그인/가입 ----------
def profile_exists_by_student_no(student_no: str):
    client = get_user_client()
    try:
        res = (
            client.table("profiles")
            .select("id,name,school_email")
            .eq("student_no", student_no)
            .execute()
        )
    except Exception as e:
        st.error(_friendly_db_error(e))
        st.stop()
    return res.data[0] if res.data else None


def send_student_otp(school_email: str):
    client = get_user_client()
    try:
        client.auth.sign_in_with_otp({
            "email": school_email,
            "options": {"should_create_user": True},
        })
    except Exception as e:
        return False, f"인증코드 발송에 실패했습니다: {e}"
    return True, "입력하신 학교 이메일로 인증코드를 보냈습니다."


def verify_student_otp(school_email: str, code: str):
    client = get_user_client()
    try:
        auth_res = client.auth.verify_otp({
            "email": school_email,
            "token": code.strip(),
            "type": "email",
        })
    except Exception:
        return False, "인증코드가 올바르지 않거나 만료되었습니다."
    if auth_res.user is None or auth_res.session is None:
        return False, "인증코드가 올바르지 않거나 만료되었습니다."
    return True, "인증되었습니다."


def finish_student_signup(student_no: str, name: str, school_email: str, password: str):
    client = get_user_client()
    try:
        update_res = client.auth.update_user({"password": password})
    except Exception as e:
        return False, f"비밀번호 설정에 실패했습니다: {e}"
    try:
        user_res = client.auth.get_user()
        uid = user_res.user.id if user_res and user_res.user else None
    except Exception:
        uid = None
    if not uid:
        return False, "세션 정보를 확인할 수 없습니다. 처음부터 다시 시도해주세요."

    admin_client = get_admin_client()
    insert_client = admin_client if admin_client is not None else client
    try:
        insert_client.table("profiles").insert({
            "id": uid,
            "student_no": student_no,
            "school_email": school_email,
            "name": name,
            "identity": "학생",
            "is_admin": False,
        }).execute()
    except Exception as e:
        return False, f"프로필 저장에 실패했습니다: {e}"
    ss.current_user_id = uid
    ss.profile_cache = None
    try:
        session = client.auth.get_session()
    except Exception:
        session = None
    save_auth_cookies(session)
    return True, "인증이 완료되고 계정이 생성되었습니다."


def student_signin(student_no: str, password: str):
    profile = profile_exists_by_student_no(student_no)
    if not profile or not profile.get("school_email"):
        return False, "등록되지 않은 학번입니다. 학교 이메일 인증을 먼저 진행해주세요."
    client = get_user_client()
    try:
        auth_res = client.auth.sign_in_with_password(
            {"email": profile["school_email"], "password": password}
        )
    except Exception:
        return False, "학번 또는 비밀번호가 올바르지 않습니다."
    if auth_res.user is None:
        return False, "학번 또는 비밀번호가 올바르지 않습니다."
    ss.current_user_id = auth_res.user.id
    ss.profile_cache = None
    save_auth_cookies(auth_res.session)
    return True, "로그인되었습니다."


# ---------- 교직원 로그인/가입 ----------
def get_staff_code_info(code: str):
    client = get_user_client()
    try:
        res = client.table("staff_codes").select("*").eq("code", code).execute()
    except Exception as e:
        st.error(_friendly_db_error(e))
        st.stop()
    return res.data[0] if res.data else None


def staff_username_exists(username: str) -> bool:
    client = get_user_client()
    try:
        res = (
            client.table("profiles")
            .select("id")
            .eq("staff_username", username)
            .execute()
        )
    except Exception as e:
        st.error(_friendly_db_error(e))
        st.stop()
    return bool(res.data)


def staff_signup(code: str, name: str, username: str, password: str):
    username = username.strip()
    if staff_username_exists(username):
        return False, "이미 사용 중인 아이디입니다. 다른 아이디를 입력해주세요."

    client = get_user_client()
    try:
        auth_res = client.auth.sign_up(
            {"email": staff_login_email(username), "password": password}
        )
    except Exception as e:
        return False, f"계정 생성에 실패했습니다: {e}"
    user = auth_res.user
    if user is None or auth_res.session is None:
        return False, (
            "계정은 만들어졌지만 로그인 세션이 발급되지 않았습니다. "
            "Supabase Authentication > Providers > Email 에서 "
            "'Confirm email' 옵션이 꺼져 있는지 확인해주세요."
        )

    admin_client = get_admin_client()
    insert_client = admin_client if admin_client is not None else client
    try:
        insert_client.table("profiles").insert({
            "id": user.id,
            "staff_code": code,
            "staff_username": username,
            "name": name,
            "identity": "교직원",
            "is_admin": False,
        }).execute()
        insert_client.table("staff_codes").update({"used_by": user.id}).eq("code", code).execute()
    except Exception as e:
        return False, f"프로필 저장에 실패했습니다: {e}"
    ss.current_user_id = user.id
    ss.profile_cache = None
    save_auth_cookies(auth_res.session)
    return True, "계정이 생성되고 로그인되었습니다."


def staff_signin(username: str, password: str):
    client = get_user_client()
    try:
        auth_res = client.auth.sign_in_with_password(
            {"email": staff_login_email(username), "password": password}
        )
    except Exception:
        return False, "아이디 또는 비밀번호가 올바르지 않습니다."
    if auth_res.user is None:
        return False, "아이디 또는 비밀번호가 올바르지 않습니다."
    ss.current_user_id = auth_res.user.id
    ss.profile_cache = None
    save_auth_cookies(auth_res.session)
    return True, "로그인되었습니다."


def logout():
    try:
        get_user_client().auth.sign_out()
    except Exception:
        pass
    ss.current_user_id = None
    ss.profile_cache = None
    reset_login_steps()
    clear_auth_cookies()
    go("메인")


# ----------------------------------------------------------------------
# 상단바 + 우측 슬라이드 드로어(햄버거 메뉴)
# ----------------------------------------------------------------------
PUBLIC_PAGES = [
    ("메인", "🏠", "home"), ("축제 안내", "🎉", "intro"), ("프로그램", "🎤", "programs"),
    ("시간표", "📅", "schedule"), ("부스 정보", "🏪", "booths"), ("오시는 길", "📍", "directions"),
    ("공지사항", "📢", "notices"),
]

# 사이드바(드로어) 메뉴에만 노출되는 페이지들.
#   - "인사말": 별도 페이지
#   - "프로그램 구성": 요청에 따라 사이드바에만 노출. 실제로는 기존 "프로그램"
#     페이지로 연결됩니다(그 페이지 안에서 관리자는 등록/수정/삭제,
#     일반 방문자는 조회를 할 수 있습니다).
DRAWER_ONLY_PAGES = [
    ("인사말", "💌", "greeting"),
    ("프로그램 구성", "🗂️", "program_manage"),
]

SLUG_BY_NAME = {name: slug for (name, icon, slug) in PUBLIC_PAGES + DRAWER_ONLY_PAGES}

NAV_SLUGS = {slug: name for (name, icon, slug) in PUBLIC_PAGES + DRAWER_ONLY_PAGES}
NAV_SLUGS.update({"login": "로그인", "mypage": "마이페이지", "admin": "관리자 페이지",
                   "booth_add": "부스 등록", "notice_add": "공지사항 등록",
                   "program_add": "프로그램 등록", "schedule_add": "시간표 등록",
                   "program_manage": "프로그램",  # 사이드바 '프로그램 구성' → 프로그램 페이지로 연결
                   "logout": "__logout__"})


def handle_nav_query_param():
    qp = st.query_params
    slug = qp.get("nav")
    if slug:
        target = NAV_SLUGS.get(slug)
        if target == "__logout__":
            logout()
        elif target:
            go(target)
        st.query_params.clear()


def render_topbar_and_drawer():
    user = current_user()
    admin = is_admin()

    links_html = ""
    for name, icon, slug in PUBLIC_PAGES:
        if name == "메인":
            continue
        target_name = NAV_SLUGS.get(slug, name)
        active = " bk-active" if ss.page == target_name else ""
        links_html += f'<a class="bk-drawer-link{active}" href="?nav={slug}" target="_self">{icon} {name}</a>'

    for name, icon, slug in DRAWER_ONLY_PAGES:
        target_name = NAV_SLUGS.get(slug, name)
        active = " bk-active" if ss.page == target_name else ""
        links_html += f'<a class="bk-drawer-link{active}" href="?nav={slug}" target="_self">{icon} {name}</a>'

    links_html += '<hr class="bk-drawer-divider">'

    if user is None:
        links_html += '<a class="bk-drawer-link" href="?nav=login" target="_self">🔐 로그인 / 인증</a>'
    else:
        badge = "👑 관리자" if admin else user["identity"]
        links_html += f'<div class="bk-drawer-user">{user["name"]}님 · {badge}</div>'
        active_my = " bk-active" if ss.page == "마이페이지" else ""
        links_html += f'<a class="bk-drawer-link{active_my}" href="?nav=mypage" target="_self">👤 마이페이지</a>'
        if admin:
            active_admin = " bk-active" if ss.page == "관리자 페이지" else ""
            links_html += f'<a class="bk-drawer-link{active_admin}" href="?nav=admin" target="_self">👑 관리자 페이지</a>'
        links_html += '<a class="bk-drawer-link" href="?nav=logout" target="_self">🚪 로그아웃</a>'

    html = f"""
    <input type="checkbox" id="bk-drawer-toggle" class="bk-drawer-checkbox">
    <div class="bk-topbar">
        <a class="bk-brand" href="?nav=home" target="_self" style="text-decoration:none;">
            <img src="{LOGO_DATA_URI}" class="bk-brand-logo" alt="경복고등학교 로고">
            <span>경복고등학교 {FESTIVAL_NAME}</span>
        </a>
        <label for="bk-drawer-toggle" class="bk-hamburger">☰</label>
    </div>
    <label for="bk-drawer-toggle" class="bk-backdrop"></label>
    <nav class="bk-drawer">
        <div class="bk-drawer-head">
            <span>메뉴</span>
            <label for="bk-drawer-toggle" class="bk-drawer-close">✕</label>
        </div>
        {links_html}
    </nav>
    """
    st.markdown(html, unsafe_allow_html=True)


# ----------------------------------------------------------------------
# 페이지 : 메인
# ----------------------------------------------------------------------
def page_main():
    hc1, hc2 = st.columns([2.6, 1])
    with hc1:
        st.markdown(
            f"""
            <div class="bk-hero">
                <div class="eyebrow">2025</div>
                <h1>경복고등학교 {FESTIVAL_NAME}</h1>
                <div class="slogan">{FESTIVAL_SLOGAN}</div>
                <div class="meta">📅 {FESTIVAL_DATE.strftime('%Y. %m. %d')}(금)</div>
                <div class="meta">📍 경복고등학교 교내 일대</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hc2:
        render_dday_box()

    st.write("")
    st.markdown('<div class="bk-iconmenu">', unsafe_allow_html=True)
    icon_cols = st.columns(6)
    for col, (name, icon, slug) in zip(icon_cols, PUBLIC_PAGES[1:]):
        with col:
            if st.button(f"{icon}\n\n{name}", key=f"iconmenu-{name}", use_container_width=True):
                go(name)
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="bk-section-title">주요 메뉴</div>', unsafe_allow_html=True)
    c1, c3 = st.columns(2)

    with c1:
        st.markdown(
            f"""
            <div class="bk-card">
                <h4>🎉 축제 안내</h4>
                <div style="height:110px;border-radius:12px;margin-bottom:10px;
                            background:linear-gradient(135deg,{NAVY} 0%, {BLUE_PILL} 100%);
                            display:flex;align-items:center;justify-content:center;color:white;font-size:32px;">
                    🏫
                </div>
                <div style="color:{MUTED};font-size:13px;">
                    북악제 소개, 일정, 장소 등 모든 정보를 확인할 수 있습니다.
                </div>
                <a class="bk-card-btn" href="?nav={SLUG_BY_NAME['축제 안내']}" target="_self">자세히 보기 →</a>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        grouped_main = fetch_schedule_by_day()
        if grouped_main:
            first_day = list(grouped_main.keys())[0]
            schedule_items_html = "".join(
                f"<div style='padding:6px 0;border-bottom:1px solid #EEF0F5;font-size:13px;'>"
                f"<b>{it['time']}</b>&nbsp;&nbsp;{it['program']} "
                f"<span style='color:{MUTED};'>({it['place']})</span></div>"
                for it in grouped_main[first_day][:4]
            )
        else:
            schedule_items_html = f"<div style='color:{MUTED};font-size:13px;'>등록된 시간표가 없습니다.</div>"
        st.markdown(
            f"""
            <div class="bk-card">
                <h4>📅 시간표</h4>
                {schedule_items_html}
                <a class="bk-card-btn" href="?nav={SLUG_BY_NAME['시간표']}" target="_self">전체 시간표 보기 →</a>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="bk-section-title">📢 공지사항</div>', unsafe_allow_html=True)
    st.markdown('<div class="bk-card">', unsafe_allow_html=True)
    main_notices = fetch_notices()
    if not main_notices:
        st.write("등록된 공지사항이 없습니다.")
    for n in main_notices[:4]:
        badge = "<span class='bk-badge-new'>NEW</span>" if n.get("new") else ""
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #EEF0F5;'>"
            f"<div>{n['title']}{badge}</div><div style='color:{MUTED};font-size:13px;'>{n['date']}</div></div>",
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="bk-section-title">🏪 부스 정보</div>', unsafe_allow_html=True)
    main_booths = fetch_booths()
    if not main_booths:
        st.markdown('<div class="bk-card">등록된 부스가 아직 없습니다.</div>', unsafe_allow_html=True)
    else:
        bcols = st.columns(4)
        for col, b in zip(bcols, main_booths[:4]):
            with col:
                img_html = booth_media_html(b, height="110px")
                st.markdown(
                    f"""
                    <div class="bk-card" style="text-align:center;">
                        {img_html}
                        <div style="font-weight:800;margin-top:4px;">{b['name']}</div>
                        <div style="color:{MUTED};font-size:13px;">{b['category']}</div>
                    </div>
                    """, unsafe_allow_html=True,
                )
    if st.button("더 많은 부스 보기 →", key="btn-booths"):
        go("부스 정보"); st.rerun()

    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 축제 안내
# ----------------------------------------------------------------------
def page_intro():
    st.markdown('<div class="bk-section-title">🎉 축제 안내</div>', unsafe_allow_html=True)
    st.markdown('<div class="bk-card">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div style="height:160px;border-radius:12px;margin-bottom:16px;
                    background:linear-gradient(135deg,{NAVY} 0%, {BLUE_PILL} 100%);
                    display:flex;align-items:center;justify-content:center;color:white;font-size:52px;">
            🏫
        </div>
        """, unsafe_allow_html=True,
    )
    st.markdown(f"""
**북악제 소개**
경복고등학교의 대표 축제인 **{FESTIVAL_NAME}**는 학생들이 직접 기획하고 준비하는
공연, 체험, 전시가 어우러진 종합 축제입니다.

**축제 일정**  {FESTIVAL_DATE.strftime('%Y년 %m월 %d일')}

**축제 장소**  경복고등학교 전 교내 (운동장, 체육관, 본관 등)

**주요 행사**  개막식·폐막식 · 동아리 공연 및 발표회 · 학급/동아리 체험 부스 · 학생 작품 전시

**문의처**  {ss.site_info['phone']}
    """)
    st.markdown('</div>', unsafe_allow_html=True)
    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 인사말 (사이드바 전용)
# ----------------------------------------------------------------------
def page_greeting():
    st.markdown('<div class="bk-section-title">💌 인사말</div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🎓 학생회장단 인사말", "🏫 교장선생님 인사말"])

    with tab1:
        st.markdown(f"""
안녕하세요, 경복고등학교 학생을 대표하는 학생회장단입니다.

먼저 저희 **{FESTIVAL_NAME}**을 찾아주신 모든 분들께 진심으로 감사드립니다.
이번 축제는 학생들이 오랜 시간 함께 고민하고 준비한 만큼, 공연·체험·전시 등
다양한 프로그램을 통해 즐거운 추억을 만드실 수 있도록 최선을 다해 준비했습니다.

학생들의 열정과 노력이 담긴 하루하루가 여러분께 즐거운 시간이 되기를 바라며,
안전하고 즐거운 축제가 될 수 있도록 끝까지 함께해 주시면 감사하겠습니다.

**"{FESTIVAL_SLOGAN}"** — 이 슬로건처럼, 우리 모두가 하나 되는 축제를 만들어가겠습니다.

감사합니다.

**경복고등학교 학생회장단 일동**
        """)

    with tab2:
        st.markdown(f"""
안녕하십니까, 경복고등학교장입니다.

한 해 동안 학업에 정진해 온 우리 학생들이 그동안 갈고닦은 끼와 재능을
마음껏 펼치는 뜻깊은 자리, **{FESTIVAL_NAME}**에 오신 것을 진심으로 환영합니다.

이 축제는 학생들이 스스로 기획하고 준비하는 과정에서 협동과 배려, 그리고
책임감을 배우는 소중한 교육의 장이기도 합니다. 학생, 학부모님, 그리고
지역사회 여러분의 관심과 성원이 있었기에 오늘의 축제가 있을 수 있었습니다.

앞으로도 학생들이 마음껏 꿈을 펼칠 수 있는 학교가 될 수 있도록
교직원 모두 최선을 다하겠습니다. 축제 기간 동안 안전에 유의하시고,
즐겁고 뜻깊은 시간 보내시기를 바랍니다.

감사합니다.

**경복고등학교장**
        """)

    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 프로그램 (사이드바 "프로그램 구성"에서도 이 페이지로 연결됩니다)
# ----------------------------------------------------------------------
def page_programs():
    st.markdown('<div class="bk-section-title">🎤 프로그램</div>', unsafe_allow_html=True)

    admin = is_admin()
    all_programs = fetch_programs()

    categories = ["전체", "공연", "체험", "전시", "기타"]
    cat = st.radio("카테고리", categories, horizontal=True, label_visibility="collapsed")
    st.markdown('<div class="bk-card">', unsafe_allow_html=True)

    filtered = all_programs if cat == "전체" else [p for p in all_programs if p["category"] == cat]
    if not filtered:
        st.info("해당 카테고리의 프로그램이 없습니다.")
    for p in filtered:
        with st.expander(f"{p['icon']}  {p['name']}  ·  {p['date']} {p['time']}  ·  {p['place']}"):
            st.markdown(f"<span class='bk-chip'>{p['category']}</span>", unsafe_allow_html=True)
            st.write(p["desc"])

            # ----------------------------------------------------------
            # 관리자에게만 보이는 수정/삭제 컨트롤 (부스/공지사항과 동일한 방식)
            # ----------------------------------------------------------
            if admin:
                st.markdown("---")
                cat_options = ["공연", "체험", "전시", "기타"]
                default_idx = cat_options.index(p["category"]) if p["category"] in cat_options else 3
                with st.form(f"program_edit_form_{p['id']}"):
                    new_name = st.text_input("프로그램 이름", value=p["name"], key=f"pg_name_{p['id']}")
                    new_cat = st.selectbox("카테고리", cat_options, index=default_idx, key=f"pg_cat_{p['id']}")
                    new_date = st.text_input("날짜", value=p["date"], key=f"pg_date_{p['id']}")
                    new_time = st.text_input("시간", value=p["time"], key=f"pg_time_{p['id']}")
                    new_place = st.text_input("장소", value=p["place"], key=f"pg_place_{p['id']}")
                    new_desc = st.text_area("설명", value=p["desc"], key=f"pg_desc_{p['id']}")
                    new_icon = st.text_input(
                        "아이콘(이모티콘)", value=p["icon"], max_chars=8, key=f"pg_icon_{p['id']}"
                    )
                    pec1, pec2 = st.columns(2)
                    save_clicked = pec1.form_submit_button("💾 저장", use_container_width=True)
                    delete_clicked = pec2.form_submit_button("🗑️ 삭제", use_container_width=True)

                if save_clicked:
                    ok, msg = update_program(p["id"], {
                        "name": new_name.strip() or p["name"], "category": new_cat,
                        "date": new_date, "time": new_time, "place": new_place,
                        "desc": new_desc, "icon": new_icon.strip() or "🎫",
                    })
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()

                if delete_clicked:
                    ok, msg = delete_program(p["id"])
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # 관리자에게만 보이는 우측 하단 + 버튼 → 프로그램 등록 페이지로 이동
    if admin:
        st.markdown(
            '<a class="bk-fab" href="?nav=program_add" target="_self" title="프로그램 추가">+</a>',
            unsafe_allow_html=True,
        )

    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 프로그램 등록 (관리자 전용, 프로그램 페이지의 + 버튼에서 진입)
# ----------------------------------------------------------------------
def page_program_add():
    if not is_admin():
        st.error("관리자만 접근할 수 있는 페이지입니다.")
        if st.button("프로그램으로 돌아가기"):
            go("프로그램"); st.rerun()
        render_footer()
        return

    st.markdown('<div class="bk-section-title">➕ 프로그램 등록</div>', unsafe_allow_html=True)
    st.markdown('<div class="bk-card">', unsafe_allow_html=True)
    with st.form("program_add_page_form"):
        pn = st.text_input("프로그램 이름")
        pcat = st.selectbox("카테고리", ["공연", "체험", "전시", "기타"])
        pdate = st.text_input("날짜", placeholder="예: 9.5(금)")
        ptime = st.text_input("시간", placeholder="예: 14:00")
        pplace = st.text_input("장소")
        pdesc = st.text_area("설명")
        picon = st.text_input("아이콘(이모티콘)", value="🎫", max_chars=8)
        c1, c2 = st.columns(2)
        submit = c1.form_submit_button("등록", use_container_width=True)
        cancel = c2.form_submit_button("취소", use_container_width=True)

    if cancel:
        go("프로그램"); st.rerun()

    if submit:
        if not pn.strip():
            st.error("프로그램 이름을 입력해주세요.")
        else:
            ok, msg = add_program({"name": pn.strip(), "category": pcat, "date": pdate,
                                    "time": ptime, "place": pplace, "desc": pdesc,
                                    "icon": picon.strip() or "🎫"})
            if ok:
                st.success(msg)
                go("프로그램"); st.rerun()
            else:
                st.error(msg)

    st.markdown('</div>', unsafe_allow_html=True)
    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 시간표
# ----------------------------------------------------------------------
def page_schedule():
    st.markdown('<div class="bk-section-title">📅 시간표</div>', unsafe_allow_html=True)
    st.caption("로그인 없이 누구나 확인할 수 있습니다.")

    admin = is_admin()
    grouped = fetch_schedule_by_day()

    st.markdown('<div class="bk-card">', unsafe_allow_html=True)
    if not grouped:
        st.info("등록된 시간표가 없습니다.")
    else:
        days = list(grouped.keys())
        tabs = st.tabs(days)
        for tab, day in zip(tabs, days):
            with tab:
                for it in grouped[day]:
                    st.markdown(
                        f"<div style='padding:8px 0;border-bottom:1px solid #EEF0F5;'>"
                        f"<span class='bk-pill'>{it['time']}</span>&nbsp;&nbsp;"
                        f"<b>{it['program']}</b> <span style='color:{MUTED};'>({it['place']})</span></div>",
                        unsafe_allow_html=True,
                    )
                    if admin:
                        with st.expander(f"✏️ 수정 / 삭제 — {it['time']} {it['program']}"):
                            with st.form(f"schedule_edit_form_{it['id']}"):
                                new_day = st.text_input("날짜", value=it["day"], key=f"sc_day_{it['id']}")
                                new_time = st.text_input("시간", value=it["time"], key=f"sc_time_{it['id']}")
                                new_program = st.text_input("프로그램", value=it["program"], key=f"sc_program_{it['id']}")
                                new_place = st.text_input("장소", value=it["place"], key=f"sc_place_{it['id']}")
                                sec1, sec2 = st.columns(2)
                                save_clicked = sec1.form_submit_button("💾 저장", use_container_width=True)
                                delete_clicked = sec2.form_submit_button("🗑️ 삭제", use_container_width=True)

                            if save_clicked:
                                ok, msg = update_schedule_item(it["id"], {
                                    "day": new_day, "time": new_time,
                                    "program": new_program, "place": new_place,
                                })
                                (st.success if ok else st.error)(msg)
                                if ok:
                                    st.rerun()

                            if delete_clicked:
                                ok, msg = delete_schedule_item(it["id"])
                                (st.success if ok else st.error)(msg)
                                if ok:
                                    st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    lines = []
    for day, items in grouped.items():
        lines.append(f"[{day}]")
        for it in items:
            lines.append(f"{it['time']}  {it['program']}  ({it['place']})")
        lines.append("")
    if lines:
        st.download_button("⬇️ 전체 시간표 다운로드", data="\n".join(lines),
                            file_name="북악제_시간표.txt", mime="text/plain")

    # 관리자에게만 보이는 우측 하단 + 버튼 → 시간표 등록 페이지로 이동
    if admin:
        st.markdown(
            '<a class="bk-fab" href="?nav=schedule_add" target="_self" title="시간표 추가">+</a>',
            unsafe_allow_html=True,
        )

    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 시간표 등록 (관리자 전용, 시간표 페이지의 + 버튼에서 진입)
# ----------------------------------------------------------------------
def page_schedule_add():
    if not is_admin():
        st.error("관리자만 접근할 수 있는 페이지입니다.")
        if st.button("시간표로 돌아가기"):
            go("시간표"); st.rerun()
        render_footer()
        return

    st.markdown('<div class="bk-section-title">➕ 시간표 등록</div>', unsafe_allow_html=True)
    st.markdown('<div class="bk-card">', unsafe_allow_html=True)
    with st.form("schedule_add_page_form"):
        sday = st.text_input("날짜", placeholder="예: 9.5(금)")
        stime = st.text_input("시간", placeholder="예: 10:00")
        sprogram = st.text_input("프로그램")
        splace = st.text_input("장소")
        c1, c2 = st.columns(2)
        submit = c1.form_submit_button("등록", use_container_width=True)
        cancel = c2.form_submit_button("취소", use_container_width=True)

    if cancel:
        go("시간표"); st.rerun()

    if submit:
        if not sday.strip() or not stime.strip() or not sprogram.strip():
            st.error("날짜, 시간, 프로그램은 필수입니다.")
        else:
            ok, msg = add_schedule_item({"day": sday.strip(), "time": stime.strip(),
                                          "program": sprogram.strip(), "place": splace})
            if ok:
                st.success(msg)
                go("시간표"); st.rerun()
            else:
                st.error(msg)

    st.markdown('</div>', unsafe_allow_html=True)
    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 부스 정보
# ----------------------------------------------------------------------
def page_booths():
    st.markdown('<div class="bk-section-title">🏪 부스 정보</div>', unsafe_allow_html=True)
    st.caption("부스 신청 기능은 제공하지 않으며, 운영 부스 정보만 안내합니다. (갤러리 기능 없음)")

    admin = is_admin()
    all_booths = fetch_booths()

    fcol1, fcol2 = st.columns([1, 2])
    with fcol1:
        categories = ["전체"] + sorted({b["category"] for b in all_booths if b.get("category")})
        selected_cat = st.selectbox("카테고리", categories, label_visibility="collapsed")
    with fcol2:
        keyword = st.text_input("부스 이름 검색", placeholder="🔍 부스 이름으로 검색", label_visibility="collapsed")

    booths = all_booths
    if selected_cat != "전체":
        booths = [b for b in booths if b.get("category") == selected_cat]
    if keyword.strip():
        kw = keyword.strip().lower()
        booths = [b for b in booths if kw in b["name"].lower()]

    if not all_booths:
        st.info("아직 등록된 부스가 없습니다.")
    elif not booths:
        st.info("조건에 맞는 부스가 없습니다.")
    else:
        cols = st.columns(2)
        for i, b in enumerate(booths):
            with cols[i % 2]:
                img_html = booth_media_html(b, height="260px")
                st.markdown(
                    f"""
                    <div class="bk-card" style="margin-bottom:8px;">
                        {img_html}
                        <div style="font-weight:800;font-size:17px;margin-top:4px;">{b['name']} <span class="bk-chip">{b['category']}</span></div>
                        <div style="color:{MUTED};margin-top:6px;">📍 {b['place']} &nbsp;|&nbsp; 🕒 {b['hours']}</div>
                        <div style="margin-top:8px;">{b['desc']}</div>
                    </div>
                    """, unsafe_allow_html=True,
                )

                if admin:
                    with st.expander("✏️ 이 부스 수정 / 삭제", expanded=False):
                        with st.form(f"booth_page_edit_form_{b['id']}"):
                            new_name = st.text_input("부스 이름", value=b["name"], key=f"bp_name_{b['id']}")
                            new_cat = st.text_input("카테고리", value=b["category"], key=f"bp_cat_{b['id']}")
                            new_place = st.text_input("위치", value=b["place"], key=f"bp_place_{b['id']}")
                            new_hours = st.text_input("운영시간", value=b["hours"], key=f"bp_hours_{b['id']}")
                            new_desc = st.text_area("설명", value=b["desc"], key=f"bp_desc_{b['id']}")
                            new_icon = st.text_input(
                                "아이콘(이모티콘)", value=b.get("icon") or "🏪",
                                max_chars=8, key=f"bp_icon_{b['id']}",
                                help="사진을 등록해도 이 아이콘이 사진 위 배지로 함께 표시됩니다. 예: 🍔 🎮 🎨 🎵",
                            )
                            new_image = st.file_uploader(
                                "부스 사진 교체 (선택, 비워두면 기존 사진 유지)",
                                type=["png", "jpg", "jpeg", "gif", "webp"],
                                key=f"bp_image_{b['id']}",
                            )
                            remove_image = st.checkbox(
                                "기존 사진 삭제하고 이모티콘으로 표시",
                                value=False, key=f"bp_remove_image_{b['id']}",
                            ) if b.get("image") else False
                            bec1, bec2 = st.columns(2)
                            save_clicked = bec1.form_submit_button("💾 저장", use_container_width=True)
                            delete_clicked = bec2.form_submit_button("🗑️ 삭제", use_container_width=True)

                        if save_clicked:
                            update_data = {
                                "name": new_name.strip() or b["name"],
                                "category": new_cat,
                                "place": new_place,
                                "hours": new_hours,
                                "desc": new_desc,
                                "icon": new_icon.strip() or "🏪",
                            }
                            if remove_image:
                                update_data["image"] = None
                            elif new_image is not None:
                                b64 = base64.b64encode(new_image.getvalue()).decode("utf-8")
                                update_data["image"] = f"data:{new_image.type};base64,{b64}"
                            ok, msg = update_booth(b["id"], update_data)
                            (st.success if ok else st.error)(msg)
                            if ok:
                                st.rerun()

                        if delete_clicked:
                            ok, msg = delete_booth(b["id"])
                            (st.success if ok else st.error)(msg)
                            if ok:
                                st.rerun()

    if admin:
        st.markdown(
            '<a class="bk-fab" href="?nav=booth_add" target="_self" title="부스 추가">+</a>',
            unsafe_allow_html=True,
        )

    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 부스 등록 (관리자 전용, 부스 정보 페이지의 + 버튼에서 진입)
# ----------------------------------------------------------------------
def page_booth_add():
    if not is_admin():
        st.error("관리자만 접근할 수 있는 페이지입니다.")
        if st.button("부스 정보로 돌아가기"):
            go("부스 정보"); st.rerun()
        render_footer()
        return

    st.markdown('<div class="bk-section-title">➕ 부스 등록</div>', unsafe_allow_html=True)
    st.markdown('<div class="bk-card">', unsafe_allow_html=True)
    with st.form("booth_add_page_form"):
        bn = st.text_input("부스 이름")
        bc = st.text_input("카테고리 (예: 음식/게임/체험/전시)")
        bp = st.text_input("위치")
        bh = st.text_input("운영시간")
        bd = st.text_area("설명")
        b_icon = st.text_input(
            "아이콘(이모티콘)", value="🏪", max_chars=8,
            help="사진을 등록해도 이 아이콘이 사진 위 배지로 함께 표시됩니다. 예: 🍔 🎮 🎨 🎵 ☕",
        )
        b_image = st.file_uploader(
            "부스 사진 (선택, 등록하면 사진과 아이콘이 함께 표시됩니다)",
            type=["png", "jpg", "jpeg", "gif", "webp"], key="booth_add_page_image"
        )
        c1, c2 = st.columns(2)
        submit = c1.form_submit_button("등록", use_container_width=True)
        cancel = c2.form_submit_button("취소", use_container_width=True)

    if cancel:
        go("부스 정보"); st.rerun()

    if submit:
        if not bn.strip():
            st.error("부스 이름을 입력해주세요.")
        else:
            image_data_uri = None
            if b_image is not None:
                b64 = base64.b64encode(b_image.getvalue()).decode("utf-8")
                image_data_uri = f"data:{b_image.type};base64,{b64}"
            ok, msg = add_booth({"name": bn.strip(), "category": bc, "place": bp,
                                  "hours": bh, "desc": bd, "icon": b_icon.strip() or "🏪",
                                  "image": image_data_uri})
            if ok:
                st.success(msg)
                go("부스 정보"); st.rerun()
            else:
                st.error(msg)

    st.markdown('</div>', unsafe_allow_html=True)
    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 오시는 길
# ----------------------------------------------------------------------
def page_directions():
    st.markdown('<div class="bk-section-title">📍 오시는 길</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.4, 1])
    with c1:
        st.map(data={"lat": [37.5807], "lon": [126.9701]})
    with c2:
        st.markdown('<div class="bk-card">', unsafe_allow_html=True)
        st.write(f"**주소**\n\n{ss.site_info['address']}")
        st.markdown("---")
        st.write(f"🚇 **지하철**\n\n{ss.site_info['subway']}")
        st.write(f"🚌 **버스**\n\n{ss.site_info['bus']}")
        st.write(f"🚶 **도보**\n\n{ss.site_info['walk']}")
        st.markdown('</div>', unsafe_allow_html=True)
    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 공지사항
# ----------------------------------------------------------------------
def page_notices():
    st.markdown('<div class="bk-section-title">📢 공지사항</div>', unsafe_allow_html=True)

    admin = is_admin()
    notices = fetch_notices()

    st.markdown('<div class="bk-card">', unsafe_allow_html=True)
    if not notices:
        st.info("등록된 공지사항이 없습니다.")
    else:
        for n in notices:
            badge = "<span class='bk-badge-new'>NEW</span>" if n.get("new") else ""
            with st.expander(f"{n['title']}   ({n['date']})"):
                st.markdown(badge, unsafe_allow_html=True)
                st.write(n["content"])

                if admin:
                    st.markdown("---")
                    with st.form(f"notice_page_edit_form_{n['id']}"):
                        new_title = st.text_input("제목", value=n["title"], key=f"np_title_{n['id']}")
                        new_content = st.text_area("내용", value=n["content"], key=f"np_content_{n['id']}")
                        new_is_new = st.checkbox("NEW 표시", value=bool(n.get("new")), key=f"np_new_{n['id']}")
                        nec1, nec2 = st.columns(2)
                        save_clicked = nec1.form_submit_button("💾 저장", use_container_width=True)
                        delete_clicked = nec2.form_submit_button("🗑️ 삭제", use_container_width=True)

                    if save_clicked:
                        ok, msg = update_notice(n["id"], new_title.strip() or n["title"], new_content, new_is_new)
                        (st.success if ok else st.error)(msg)
                        if ok:
                            st.rerun()

                    if delete_clicked:
                        ok, msg = delete_notice(n["id"])
                        (st.success if ok else st.error)(msg)
                        if ok:
                            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if admin:
        st.markdown(
            '<a class="bk-fab" href="?nav=notice_add" target="_self" title="공지사항 추가">+</a>',
            unsafe_allow_html=True,
        )

    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 공지사항 등록 (관리자 전용, 공지사항 페이지의 + 버튼에서 진입)
# ----------------------------------------------------------------------
def page_notice_add():
    if not is_admin():
        st.error("관리자만 접근할 수 있는 페이지입니다.")
        if st.button("공지사항으로 돌아가기"):
            go("공지사항"); st.rerun()
        render_footer()
        return

    st.markdown('<div class="bk-section-title">➕ 공지사항 등록</div>', unsafe_allow_html=True)
    st.markdown('<div class="bk-card">', unsafe_allow_html=True)
    with st.form("notice_add_page_form"):
        t = st.text_input("제목")
        c = st.text_area("내용")
        is_new = st.checkbox("NEW 표시", value=True)
        c1, c2 = st.columns(2)
        submit = c1.form_submit_button("등록", use_container_width=True)
        cancel = c2.form_submit_button("취소", use_container_width=True)

    if cancel:
        go("공지사항"); st.rerun()

    if submit:
        if not t.strip():
            st.error("제목을 입력해주세요.")
        else:
            ok, msg = add_notice(t.strip(), c, is_new)
            if ok:
                st.success(msg)
                go("공지사항"); st.rerun()
            else:
                st.error(msg)

    st.markdown('</div>', unsafe_allow_html=True)
    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 로그인 / 인증  (학생: 학번+비밀번호 / 교직원: 아이디+비밀번호, Supabase Auth)
# ----------------------------------------------------------------------
def page_login():
    st.markdown('<div class="bk-section-title">🔐 로그인 / 인증</div>', unsafe_allow_html=True)

    user = current_user()
    if user is not None:
        st.info(f"이미 **{user['name']}**님으로 로그인되어 있습니다.")
        if st.button("마이페이지로 이동"):
            go("마이페이지"); st.rerun()
        render_footer()
        return

    st.markdown('<div class="bk-card">', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["👤 학생 인증", "🧑‍🏫 교직원 인증"])

    with tab1:
        if ss.student_step == "check":
            st.caption("학번과 이름을 입력해주세요. 처음이라면 학교이메일 인증을 진행하게 됩니다.")
            with st.form("student_check_form"):
                s_no = st.text_input("학번(학교아이디)", placeholder="예: 20301")
                s_name = st.text_input("이름")
                submitted = st.form_submit_button("다음", use_container_width=True)
            if submitted:
                if not s_no or not s_name:
                    st.error("학번과 이름을 모두 입력해주세요.")
                else:
                    existing = profile_exists_by_student_no(s_no.strip())
                    ss.pending_student_no = s_no.strip()
                    ss.pending_student_name = s_name.strip()
                    ss.student_step = "password_existing" if existing else "email_input"
                    st.rerun()

        elif ss.student_step == "email_input":
            st.success(f"학번 **{ss.pending_student_no}**({ss.pending_student_name})은(는) 처음 로그인합니다. 학교 이메일을 입력해주세요.")
            with st.form("student_email_form"):
                s_email = st.text_input("학교 이메일", placeholder="예: 20301@kbhs.hs.kr")
                c1, c2 = st.columns(2)
                submit = c1.form_submit_button("인증코드 받기", use_container_width=True)
                back = c2.form_submit_button("← 뒤로", use_container_width=True)
            if back:
                reset_login_steps(); st.rerun()
            if submit:
                if not s_email or "@" not in s_email:
                    st.error("학교 이메일을 올바르게 입력해주세요.")
                else:
                    ok, msg = send_student_otp(s_email.strip())
                    if ok:
                        ss.pending_student_email = s_email.strip()
                        ss.student_step = "otp_verify"
                        st.rerun()
                    else:
                        st.error(msg)

        elif ss.student_step == "otp_verify":
            st.write(f"**{ss.pending_student_email}** 로 전송된 인증코드를 입력해주세요.")
            with st.form("student_otp_form"):
                code = st.text_input("인증코드 (6자리)")
                c1, c2, c3 = st.columns(3)
                submit = c1.form_submit_button("확인", use_container_width=True)
                resend = c2.form_submit_button("재전송", use_container_width=True)
                back = c3.form_submit_button("← 뒤로", use_container_width=True)
            if back:
                reset_login_steps(); st.rerun()
            if resend:
                ok, msg = send_student_otp(ss.pending_student_email)
                (st.success if ok else st.error)(msg)
            if submit:
                if not code:
                    st.error("인증코드를 입력해주세요.")
                else:
                    ok, msg = verify_student_otp(ss.pending_student_email, code)
                    if ok:
                        ss.student_step = "password_new"
                        st.rerun()
                    else:
                        st.error(msg)

        elif ss.student_step == "password_new":
            st.success("이메일 인증이 완료되었습니다. 앞으로 로그인에 사용할 비밀번호를 만들어주세요.")
            with st.form("student_signup_form"):
                pw1 = st.text_input("비밀번호 (6자 이상)", type="password")
                pw2 = st.text_input("비밀번호 확인", type="password")
                submit = st.form_submit_button("계정 생성 및 로그인", use_container_width=True)
            if submit:
                if len(pw1) < 6:
                    st.error("비밀번호는 6자 이상이어야 합니다.")
                elif pw1 != pw2:
                    st.error("비밀번호가 서로 일치하지 않습니다.")
                else:
                    ok, msg = finish_student_signup(
                        ss.pending_student_no, ss.pending_student_name,
                        ss.pending_student_email, pw1,
                    )
                    if ok:
                        reset_login_steps()
                        st.success(msg)
                        go("마이페이지"); st.rerun()
                    else:
                        st.error(msg)

        elif ss.student_step == "password_existing":
            st.write(f"**{ss.pending_student_name}**님, 비밀번호를 입력해주세요.")
            with st.form("student_signin_form"):
                pw = st.text_input("비밀번호", type="password")
                c1, c2 = st.columns(2)
                submit = c1.form_submit_button("로그인", use_container_width=True)
                back = c2.form_submit_button("← 뒤로", use_container_width=True)
            if back:
                reset_login_steps(); st.rerun()
            if submit:
                ok, msg = student_signin(ss.pending_student_no, pw)
                if ok:
                    reset_login_steps()
                    go("마이페이지"); st.rerun()
                else:
                    st.error(msg)

    with tab2:
        staff_sub1, staff_sub2 = st.tabs(["🆕 최초 등록 (인증코드)", "🔑 로그인 (아이디)"])

        with staff_sub1:
            if ss.staff_step == "check":
                st.caption("미리 발급받은 교직원 인증코드를 입력해주세요. (최초 1회만 필요합니다)")
                with st.form("staff_check_form"):
                    code = st.text_input("인증코드", placeholder="예: BK26-A7Q9")
                    submitted = st.form_submit_button("다음", use_container_width=True)
                if submitted:
                    code = code.strip()
                    info = get_staff_code_info(code)
                    if not info:
                        st.error("존재하지 않는 인증코드입니다.")
                    elif not info["active"]:
                        st.error("비활성화된 인증코드입니다.")
                    elif info.get("used_by"):
                        st.error("이미 등록에 사용된 인증코드입니다. '로그인 (아이디)' 탭에서 아이디+비밀번호로 로그인해주세요.")
                    else:
                        preset_name = (info.get("name") or "").strip()
                        if not preset_name:
                            st.error("이 인증코드에는 담당 선생님 이름이 등록되어 있지 않습니다. 관리자에게 문의해주세요.")
                        else:
                            ss.pending_staff_code = code
                            ss.pending_staff_name = preset_name
                            ss.staff_step = "account_new"
                            st.rerun()

            elif ss.staff_step == "account_new":
                st.success(f"인증코드 확인 완료 — **{ss.pending_staff_name}**님, 앞으로 로그인에 사용할 아이디와 비밀번호를 만들어주세요.")
                with st.form("staff_signup_form"):
                    s_username = st.text_input("아이디(로그인 ID)", placeholder="예: kimteacher")
                    pw1 = st.text_input("비밀번호 (6자 이상)", type="password")
                    pw2 = st.text_input("비밀번호 확인", type="password")
                    c1, c2 = st.columns(2)
                    submit = c1.form_submit_button("계정 생성 및 로그인", use_container_width=True)
                    back = c2.form_submit_button("← 뒤로", use_container_width=True)
                if back:
                    reset_login_steps(); st.rerun()
                if submit:
                    if not s_username.strip():
                        st.error("아이디를 입력해주세요.")
                    elif len(pw1) < 6:
                        st.error("비밀번호는 6자 이상이어야 합니다.")
                    elif pw1 != pw2:
                        st.error("비밀번호가 서로 일치하지 않습니다.")
                    else:
                        ok, msg = staff_signup(
                            ss.pending_staff_code, ss.pending_staff_name, s_username, pw1,
                        )
                        if ok:
                            reset_login_steps()
                            st.success(msg)
                            go("마이페이지"); st.rerun()
                        else:
                            st.error(msg)

        with staff_sub2:
            st.caption("이미 인증코드로 등록을 마치셨다면, 그때 만든 아이디+비밀번호로 로그인해주세요.")
            with st.form("staff_signin_form"):
                login_username = st.text_input("아이디")
                pw = st.text_input("비밀번호", type="password")
                submit = st.form_submit_button("로그인", use_container_width=True)
            if submit:
                if not login_username.strip():
                    st.error("아이디를 입력해주세요.")
                else:
                    ok, msg = staff_signin(login_username.strip(), pw)
                    if ok:
                        reset_login_steps()
                        go("마이페이지"); st.rerun()
                    else:
                        st.error(msg)

    st.markdown('</div>', unsafe_allow_html=True)
    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 마이페이지
# ----------------------------------------------------------------------
def page_mypage():
    user = current_user()
    if user is None:
        if ss.get("current_user_id"):
            st.error("로그인은 되어 있지만 프로필 정보를 불러오지 못했습니다.")
            if ss.get("last_profile_error"):
                st.caption(f"상세: {ss.last_profile_error}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("다시 시도"):
                    ss.profile_cache = None
                    st.rerun()
            with c2:
                if st.button("로그아웃 후 다시 로그인"):
                    logout(); st.rerun()
        else:
            st.warning("로그인이 필요합니다. 우측 상단 ☰ 메뉴에서 학생/교직원 인증을 진행해주세요.")
            if st.button("로그인 / 인증 하러 가기"):
                go("로그인"); st.rerun()
        render_footer()
        return

    st.markdown('<div class="bk-section-title">👤 마이페이지</div>', unsafe_allow_html=True)

    role_menus = {
        "학생": ["내 정보", "신청 내역", "시간표", "설문 참여 내역", "알림", "개인정보 설정", "로그아웃"],
        "교직원": ["내 정보", "교직원 전용 기능", "시간표", "알림", "개인정보 설정", "로그아웃"],
    }
    menu = role_menus.get(user["identity"], [])
    if user["is_admin"]:
        menu = ["👑 관리자 페이지"] + menu

    st.markdown('<div class="bk-card">', unsafe_allow_html=True)
    st.markdown(f"### {'👑' if user['is_admin'] else ('🎓' if user['identity']=='학생' else '🧑‍🏫')} {user['name']}")
    if user.get("student_no"):
        id_line = f"학번 {user['student_no']}"
    elif user.get("staff_username"):
        id_line = f"아이디 {user['staff_username']}"
    else:
        id_line = f"인증코드 {user.get('staff_code','-')}"
    st.write(f"**신분**: {user['identity']} ({id_line})  ·  **관리자 권한**: {'있음 👑' if user['is_admin'] else '없음'}")
    st.markdown("---")
    mcols = st.columns(3)
    for i, m in enumerate(menu):
        with mcols[i % 3]:
            st.markdown(f"<div class='bk-chip' style='margin-bottom:8px;'>{m}</div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if user["is_admin"]:
        st.write("")
        if st.button("👑 관리자 페이지로 이동"):
            go("관리자 페이지"); st.rerun()

    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 관리자 페이지
# ----------------------------------------------------------------------
def page_admin():
    st.markdown('<div class="bk-section-title">👑 관리자 페이지</div>', unsafe_allow_html=True)
    st.markdown(
        f"<div style='color:{MUTED};margin-bottom:10px;'>※ 관리자 권한 부여/회수, 인증코드 발급은 서비스 키(SUPABASE_SERVICE_KEY)가 설정되어 있어야 동작합니다.</div>",
        unsafe_allow_html=True,
    )
    admin_client = get_admin_client()
    if admin_client is None:
        st.warning("`secrets.toml` 에 `SUPABASE_SERVICE_KEY` 가 없어 일부 관리 기능(권한 부여/회수, 인증코드 발급, 공지/부스/프로그램/시간표 등록·수정·삭제)이 비활성화되어 있습니다.")

    tabs = st.tabs(["🧑‍💻 사용자 관리", "🔑 권한 관리", "🔒 인증코드 관리", "📊 방문자 통계"])

    with tabs[0]:
        st.markdown('<div class="bk-card">', unsafe_allow_html=True)
        st.subheader("사용자 목록")
        client = get_user_client()
        try:
            res = client.table("profiles").select(
                "id,name,identity,is_admin,student_no,staff_code,staff_username"
            ).execute()
            users = res.data or []
        except Exception as e:
            st.error(_friendly_db_error(e))
            users = []
        if not users:
            st.info("등록된 사용자가 없습니다.")
        else:
            rows = [{"ID": u["id"], "이름": u["name"], "신분": u["identity"],
                     "학번/아이디": u.get("student_no") or u.get("staff_username") or "-",
                     "관리자": "✅" if u["is_admin"] else ""} for u in users]
            st.dataframe(rows, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with tabs[1]:
        st.markdown('<div class="bk-card">', unsafe_allow_html=True)
        st.subheader("관리자 권한 부여 / 회수")
        client = get_user_client()
        try:
            res = client.table("profiles").select("id,name,identity").execute()
            users = res.data or []
        except Exception as e:
            st.error(_friendly_db_error(e))
            users = []
        if not users:
            st.info("등록된 사용자가 없습니다.")
        elif admin_client is None:
            st.info("SUPABASE_SERVICE_KEY가 설정되면 이 기능을 사용할 수 있습니다.")
        else:
            target = st.selectbox("대상 사용자", [u["id"] for u in users],
                                   format_func=lambda uid: next(f"{u['name']} ({u['identity']})" for u in users if u["id"] == uid))
            c1, c2 = st.columns(2)
            with c1:
                if st.button("👑 관리자 권한 부여"):
                    admin_client.table("profiles").update({"is_admin": True}).eq("id", target).execute()
                    st.success("관리자 권한을 부여했습니다."); st.rerun()
            with c2:
                if st.button("🚫 관리자 권한 회수"):
                    admin_client.table("profiles").update({"is_admin": False}).eq("id", target).execute()
                    st.success("관리자 권한을 회수했습니다."); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with tabs[2]:
        st.markdown('<div class="bk-card">', unsafe_allow_html=True)
        st.subheader("교직원 인증코드 목록")
        client = get_user_client()
        try:
            res = client.table("staff_codes").select("*").execute()
            codes = res.data or []
        except Exception as e:
            st.error(_friendly_db_error(e))
            codes = []

        rows = [{"인증코드": c["code"], "담당자(사전등록)": c.get("name") or "-",
                 "상태": "활성" if c["active"] else "비활성",
                 "사용여부": "사용됨" if c["used_by"] else "미사용"} for c in codes]
        st.dataframe(rows, use_container_width=True)

        if admin_client is None:
            st.info("SUPABASE_SERVICE_KEY가 설정되면 인증코드 발급/비활성화를 사용할 수 있습니다.")
        else:
            import random, string
            st.markdown("**새 인증코드 발급**")
            with st.form("staff_code_new_form"):
                new_code_name = st.text_input("담당 선생님 이름", placeholder="예: 김철수")
                gen_submit = st.form_submit_button("➕ 새 인증코드 생성", use_container_width=True)
            if gen_submit:
                if not new_code_name.strip():
                    st.error("담당 선생님 이름을 입력해주세요. 최초 등록 시 이 이름이 자동으로 사용됩니다.")
                else:
                    new_code = "BK26-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
                    admin_client.table("staff_codes").insert(
                        {"code": new_code, "name": new_code_name.strip(), "active": True}
                    ).execute()
                    st.success(f"새 인증코드: {new_code} (담당: {new_code_name.strip()})"); st.rerun()
            if codes:
                target_code = st.selectbox("비활성화할 인증코드", ["선택 안함"] + [c["code"] for c in codes])
                if target_code != "선택 안함" and st.button("인증코드 비활성화"):
                    admin_client.table("staff_codes").update({"active": False}).eq("code", target_code).execute()
                    st.success("비활성화했습니다."); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with tabs[3]:
        st.markdown('<div class="bk-card">', unsafe_allow_html=True)
        st.subheader("방문자 통계")
        st.caption("브라우저 세션(탭)당 1회 기록됩니다. IP 등 개인 식별 정보는 저장하지 않습니다.")

        total = fetch_visit_total()
        st.metric("누적 방문 수(세션 기준)", f"{total:,}")

        daily = fetch_visit_daily(days=14)
        if daily:
            st.markdown("**최근 14일 일별 방문자 추이**")
            st.bar_chart(daily)
        else:
            st.info("아직 최근 14일간의 방문 기록이 없습니다.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.caption("📢 공지사항/부스/프로그램/시간표 등록·수정·삭제는 각각의 메뉴 화면에서 직접 할 수 있습니다 "
               "(각 카드/항목 안에서 수정·삭제, 우측 하단 + 버튼으로 신규 등록).")

    render_footer()


# ----------------------------------------------------------------------
# 푸터
# ----------------------------------------------------------------------
def render_footer():
    st.markdown(
        f"""
        <div class="bk-footer">
            <b>📮 문의 및 안내</b><br>
            📞 {ss.site_info['phone']} &nbsp;|&nbsp; ✉️ {ss.site_info['email']} &nbsp;|&nbsp; 🕒 {ss.site_info['hours']}<br>
            🏫 경복고등학교 학생회
        </div>
        """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------
# 라우팅
# ----------------------------------------------------------------------
def main():
    record_visit()
    handle_nav_query_param()
    render_topbar_and_drawer()

    routes = {
        "메인": page_main, "축제 안내": page_intro, "프로그램": page_programs,
        "시간표": page_schedule, "부스 정보": page_booths, "오시는 길": page_directions,
        "공지사항": page_notices, "인사말": page_greeting,
        "로그인": page_login, "마이페이지": page_mypage, "관리자 페이지": page_admin,
        "부스 등록": page_booth_add, "공지사항 등록": page_notice_add,
        "프로그램 등록": page_program_add, "시간표 등록": page_schedule_add,
    }

    if ss.page == "마이페이지" and current_user() is None and not ss.get("current_user_id"):
        st.warning("로그인이 필요합니다."); return
    if ss.page == "관리자 페이지" and not is_admin():
        if ss.get("current_user_id") and current_user() is None:
            st.error("로그인은 되어 있지만 프로필 정보를 불러오지 못해 관리자 권한을 확인할 수 없습니다.")
            if ss.get("last_profile_error"):
                st.caption(f"상세: {ss.last_profile_error}")
        else:
            st.error("관리자 권한이 없습니다.")
        return

    routes.get(ss.page, page_main)()


if __name__ == "__main__":
    main()
