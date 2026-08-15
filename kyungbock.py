# -*- coding: utf-8 -*-
"""
경복고등학교 북악제 축제 홈페이지 (Supabase 로그인 연동판)
Streamlit 기반 반응형 웹앱

로그인 방식
    - 학생: 학번+이름 → (최초 1회) 학교이메일로 인증코드(OTP) 발송/확인 → 비밀번호 생성
            → 이후에는 학번+비밀번호로 로그인 (내부적으로 저장된 학교이메일로 인증)
    - 교직원: 인증코드 → (최초 1회) 이름+비밀번호 생성 → 이후 코드+비밀번호로 로그인
            (교직원은 실제 이메일이 없으므로 "코드 + 가짜 이메일"로 Supabase Auth 계정을 만듭니다)

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
[수정 사항 - 메인 페이지 카드 렌더링 버그 수정]
기존 코드는 아래처럼 div 여는 태그/닫는 태그를 여러 st.markdown 호출로
나눠 작성했습니다.

    st.markdown('<div class="bk-card">', unsafe_allow_html=True)
    st.markdown("#### 제목")
    ...
    if st.button("자세히 보기 →"):
        ...
    st.markdown('</div>', unsafe_allow_html=True)

Streamlit은 각 st.markdown / st.button 호출을 서로 다른 "형제(sibling)"
DOM 블록으로 렌더링하기 때문에, 이렇게 나눠 쓴 여는/닫는 div는 실제로는
서로 감싸지 못합니다. 그 결과 배경 카드(bk-card)만 빈 채로 렌더링되고,
제목/내용/버튼은 카드 밖에 스타일 없이 따로 표시되는 문제가 있었습니다.

해결: 카드 하나를 "한 번의 st.markdown 호출"로 통째로 렌더링하도록
변경했습니다. 카드 안의 "자세히 보기" 버튼은 st.button(네이티브 위젯)
대신, 이미 드로어 메뉴에서 쓰고 있던 것과 같은 방식인
`<a href="?nav=슬러그" target="_self">` 앵커 링크로 대체했습니다.
----------------------------------------------------------------------

----------------------------------------------------------------------
[수정 사항 2 - 새로고침 시 로그인이 풀리는 문제 해결]
기존 코드는 로그인 상태(current_user_id)를 st.session_state 에만
저장했습니다. st.session_state 는 "브라우저 탭의 서버 프로세스 메모리"에
있는 값이라, 사용자가 주소창에 URL을 다시 입력하거나 브라우저를
새로고침(F5)하면 Streamlit이 그 탭에 대해 완전히 새로운 세션을 만들어
버리고, current_user_id 가 다시 None으로 초기화되어 로그인이 풀립니다.

해결: Supabase Auth 세션(access_token/refresh_token)을 브라우저 쿠키에
저장했다가, 앱이 다시 로드될 때 그 토큰으로 세션을 복구합니다.
Streamlit 자체에는 쿠키 저장 기능이 없어서 `streamlit-cookies-manager`
패키지를 사용했습니다. 아래 함수들이 관련 로직입니다.
    - save_auth_cookies() : 로그인/회원가입 성공 시 토큰을 쿠키에 저장
    - clear_auth_cookies() : 로그아웃 시 쿠키 삭제
    - try_restore_session_from_cookies() : 앱 로드 시 쿠키로 세션 복구
----------------------------------------------------------------------
"""

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, date, time as dtime
from pathlib import Path

# ----------------------------------------------------------------------
# 기본 설정
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="경복고 북악제",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="collapsed",
)

FESTIVAL_NAME = "북악제"
FESTIVAL_SLOGAN = "빛나는 우리, 하나의 이야기"
FESTIVAL_DATE = date(2026, 10, 30)
# 카운트다운 기준 시각: 축제 당일 00:00 (자정)
FESTIVAL_DATETIME = datetime.combine(FESTIVAL_DATE, dtime(0, 0, 0))
FESTIVAL_TZ_OFFSET = "+09:00"  # 한국 표준시(KST) 기준

# 학번/인증코드로 만드는 가짜 이메일 도메인 (Supabase Auth 내부용, 실제 발송 안 됨)
FAKE_EMAIL_DOMAIN = "bukakje.internal"

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

# 로그인 유지(새로고침 대응)용 쿠키 매니저
try:
    from streamlit_cookies_manager import EncryptedCookieManager
except ImportError:
    st.error(
        "`streamlit-cookies-manager` 패키지가 설치되어 있지 않습니다.\n\n"
        "터미널에서 `pip install streamlit-cookies-manager` 를 실행한 뒤 다시 시작해주세요.\n\n"
        "(이 패키지가 있어야 새로고침 후에도 로그인 상태가 유지됩니다.)"
    )
    st.stop()


def _debug_secret_paths() -> str:
    """secrets.toml을 찾아본 경로와 실제로 그 폴더에 어떤 파일이 있는지 보여줍니다.
    (확장자가 .txt로 잘못 저장되는 등의 실수를 바로 찾을 수 있도록)"""
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
        # secrets.toml 파일 자체가 없을 때 st.secrets 접근 시 예외가 발생합니다.
        val = None
        if required:
            st.error(
                "`secrets.toml` 파일을 찾을 수 없습니다.\n\n"
                "다음 경로들을 확인해봤습니다.\n\n"
                f"{_debug_secret_paths()}\n\n"
                "위 목록에 `secrets.toml.txt` 처럼 확장자가 다르게 보인다면 "
                "그게 원인입니다 — 파일 이름을 `secrets.toml`로 바꿔주세요.\n\n"
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

# 쿠키 암호화 키. secrets.toml에 없으면 임시 기본값을 쓰지만,
# 그러면 서버(앱)를 재시작할 때마다 값이 달라져 기존 쿠키를 못 읽게 되므로
# secrets.toml 에 직접 넣어두는 것을 강력히 권장합니다.
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
    """브라우저 세션(탭)마다 독립된 클라이언트. 로그인 상태가 여기 실려있습니다."""
    if "sb_client" not in st.session_state:
        st.session_state.sb_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return st.session_state.sb_client


@st.cache_resource
def get_admin_client():
    """서비스 역할 키 클라이언트. RLS를 우회하므로 관리자 기능에서만 사용합니다."""
    if not SUPABASE_SERVICE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def student_email(student_no: str) -> str:
    return f"student-{student_no.strip()}@{FAKE_EMAIL_DOMAIN}"


def staff_email(code: str) -> str:
    return f"staff-{code.strip()}@{FAKE_EMAIL_DOMAIN}"


# ----------------------------------------------------------------------
# 쿠키 매니저 초기화 (로그인 유지용)
#   - EncryptedCookieManager는 브라우저에 작은 JS 컴포넌트를 심어 쿠키를
#     읽어오는데, 첫 로드 시 한 번의 렌더링 사이클이 필요합니다.
#     그래서 준비(ready)가 안 됐으면 안내 후 st.stop() 으로 대기합니다.
#     (내부적으로 자동 재실행되며, 사용자 눈에는 아주 짧은 로딩으로만 보입니다.)
# ----------------------------------------------------------------------
cookies = EncryptedCookieManager(prefix="bukakje_", password=COOKIE_PASSWORD)
if not cookies.ready():
    st.stop()


def save_auth_cookies(session):
    """Supabase Auth 세션(access_token/refresh_token)을 브라우저 쿠키에 저장합니다.
    로그인/회원가입 성공 직후 호출하면, 이후 새로고침해도 이 쿠키로 세션을
    복구할 수 있습니다."""
    if session is None:
        return
    try:
        cookies["sb_access_token"] = session.access_token or ""
        cookies["sb_refresh_token"] = session.refresh_token or ""
        cookies.save()
    except Exception:
        # 쿠키 저장 실패는 로그인 자체를 막을 이유는 아니므로 조용히 넘어갑니다.
        # (이 경우 새로고침하면 다시 로그인해야 할 뿐입니다.)
        pass


def clear_auth_cookies():
    try:
        cookies["sb_access_token"] = ""
        cookies["sb_refresh_token"] = ""
        cookies.save()
    except Exception:
        pass


def try_restore_session_from_cookies():
    """앱이 (새로고침 등으로) 새로 로드되었을 때, 쿠키에 저장된 토큰이 있으면
    Supabase Auth 세션을 복구해서 로그인 상태를 되살립니다."""
    if st.session_state.get("current_user_id"):
        return  # 이미 이번 세션에서 로그인되어 있음

    access_token = cookies.get("sb_access_token")
    refresh_token = cookies.get("sb_refresh_token")
    if not access_token or not refresh_token:
        return

    client = get_user_client()
    try:
        client.auth.set_session(access_token, refresh_token)
        user_res = client.auth.get_user()
    except Exception:
        # 토큰이 만료되었거나 유효하지 않음 → 쿠키 정리
        clear_auth_cookies()
        return

    if user_res and user_res.user:
        st.session_state.current_user_id = user_res.user.id
        st.session_state.profile_cache = None
    else:
        clear_auth_cookies()


# ----------------------------------------------------------------------
# 디자인 토큰 (목업 이미지 기반)
#  - 남색(#0F1F3D) 히어로 + 오렌지(#F2994A) 포인트 + 화이트 카드
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
    color: white;
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

/* 카드 안에서 st.button 대신 쓰는 "버튼처럼 보이는" 링크
   (여러 st.markdown 호출에 걸쳐 div를 나눠 여는 대신,
    카드 전체를 한 번의 st.markdown 호출로 렌더링하기 위함) */
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
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------------------------------------------------
# 세션 상태 초기화 (공지/프로그램/시간표/부스/사이트정보는 데모용 인메모리 유지)
#  - 로그인/사용자/권한 관련 정보만 Supabase로 이동했습니다.
# ----------------------------------------------------------------------
def init_state():
    ss = st.session_state

    if "page" not in ss:
        ss.page = "메인"

    if "current_user_id" not in ss:
        ss.current_user_id = None

    if "profile_cache" not in ss:
        ss.profile_cache = None

    # 로그인 화면 단계 상태
    if "student_step" not in ss:
        ss.student_step = "check"   # check -> email_input -> otp_verify -> password_new
                                     #       -> (기존 학번) password_existing
    if "staff_step" not in ss:
        ss.staff_step = "check"

    if "notices" not in ss:
        ss.notices = [
            {"title": "2025 북악제 프로그램 안내", "date": "2025-08-20",
             "content": "북악제 프로그램이 확정되었습니다. 시간표 메뉴에서 확인하세요.", "new": True},
            {"title": "우천 시 일정 변경 안내", "date": "2025-08-15",
             "content": "우천 시 일부 야외 프로그램은 실내로 변경됩니다.", "new": True},
            {"title": "교내 주차가 불가합니다", "date": "2025-08-10",
             "content": "축제 기간 동안 교내 주차가 제한됩니다. 대중교통을 이용해주세요.", "new": False},
            {"title": "북악제 준비 자원봉사자 모집 안내", "date": "2025-08-08",
             "content": "축제 준비를 도와줄 자원봉사자를 모집합니다.", "new": False},
        ]

    if "programs" not in ss:
        ss.programs = [
            {"name": "개막식", "category": "기타", "date": "9.5(금)", "time": "10:00",
             "place": "운동장", "desc": "북악제의 시작을 알리는 개막식입니다.", "icon": "🎊"},
            {"name": "동아리 공연", "category": "공연", "date": "9.5(금)", "time": "14:00",
             "place": "체육관", "desc": "동아리 학생들의 다채로운 공연 무대입니다.", "icon": "🎤"},
            {"name": "체험 부스", "category": "체험", "date": "9.6(토)", "time": "11:00",
             "place": "교내", "desc": "다양한 학급/동아리 체험 부스를 즐길 수 있습니다.", "icon": "🎡"},
            {"name": "작품 전시", "category": "전시", "date": "9.6(토)", "time": "10:00",
             "place": "미술실", "desc": "학생 미술 작품을 전시합니다.", "icon": "🖼️"},
            {"name": "폐막식", "category": "기타", "date": "9.6(토)", "time": "16:00",
             "place": "운동장", "desc": "축제 일정을 마무리하는 폐막식입니다.", "icon": "🎊"},
        ]

    if "schedule" not in ss:
        ss.schedule = {
            "9.5(금)": [
                {"time": "10:00", "program": "개막식", "place": "운동장"},
                {"time": "11:00", "program": "체험 프로그램", "place": "교내"},
                {"time": "14:00", "program": "동아리 공연", "place": "체육관"},
                {"time": "16:00", "program": "폐막식", "place": "운동장"},
            ],
            "9.6(토)": [
                {"time": "10:00", "program": "작품 전시", "place": "미술실"},
                {"time": "13:00", "program": "합창 공연", "place": "체육관"},
                {"time": "15:00", "program": "동아리 발표회", "place": "강당"},
            ],
        }

    if "booths" not in ss:
        ss.booths = [
            {"name": "부스 01", "category": "음식", "place": "운동장 A구역",
             "hours": "10:00 ~ 16:00", "desc": "간단한 먹거리를 판매합니다.", "icon": "🍔"},
            {"name": "부스 02", "category": "게임", "place": "운동장 B구역",
             "hours": "10:00 ~ 16:00", "desc": "재미있는 미니게임을 즐겨보세요.", "icon": "🎮"},
            {"name": "부스 03", "category": "체험", "place": "본관 1층",
             "hours": "10:00 ~ 15:00", "desc": "다양한 체험 활동을 제공합니다.", "icon": "🎨"},
            {"name": "부스 04", "category": "전시", "place": "본관 2층",
             "hours": "10:00 ~ 16:00", "desc": "학생 작품을 전시합니다.", "icon": "🖼️"},
        ]

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

# 쿠키에 저장된 토큰이 있으면 로그인 상태를 복구합니다.
# (반드시 init_state() 이후, 페이지 렌더링 이전에 호출해야 합니다.)
try_restore_session_from_cookies()


# ----------------------------------------------------------------------
# 헬퍼
# ----------------------------------------------------------------------
def go(page_name: str):
    ss.page = page_name


def reset_login_steps():
    ss.student_step = "check"
    ss.staff_step = "check"
    for k in ("pending_student_no", "pending_student_name", "pending_student_email", "pending_staff_code"):
        ss.pop(k, None)


def current_user():
    """현재 로그인한 사용자의 profiles 행. Supabase에서 조회해 세션에 캐시합니다.

    주의: uid는 있는데(=로그인은 되어 있는데) 프로필 조회 자체가 실패하는 경우와
    애초에 로그인이 안 되어 있는 경우(uid 없음)는 원인이 완전히 다릅니다.
    예전 코드는 두 경우 모두 그냥 None을 반환해서 "로그인이 필요합니다"라는
    (실제로는 틀린) 안내가 뜨는 문제가 있었습니다. 여기서는 실패 사유를
    ss.last_profile_error 에 남겨서 화면에서 구분해 보여줄 수 있게 합니다.
    """
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


def days_left():
    return (FESTIVAL_DATE - date.today()).days


def render_dday_box():
    """D-DAY 박스를 렌더링합니다.
    표시 형식 전환(며칠 남음 ↔ 시:분:초 카운트다운) 판단을
    서버(Python)가 아니라 브라우저(JS)에서 매초 다시 계산합니다.
    Streamlit은 사용자가 상호작용하기 전까지 자동으로 재실행되지 않으므로,
    이 판단을 서버에서만 하면 24시간 문턱을 넘는 순간에도 화면이 갱신되지 않고
    이전 값(예: '1일 남았습니다')에 멈춰있게 됩니다. 클라이언트에서 매초
    다시 계산하게 하면 페이지를 열어둔 채로도 자동으로 전환됩니다.
    """
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
                    // 24시간 이내: 시:분:초 카운트다운
                    // 주의: '남은 시간이 24시간보다 적다'는 것과 '오늘이다'는 다른 조건입니다.
                    // 예를 들어 축제 전날 새벽 2시라면 자정까지 22시간이 남아 이 분기를 타지만
                    // 실제로는 아직 전날이고 축제는 '내일' 시작합니다. 그래서 '오늘 시작합니다'라고
                    // 단정하지 않고 '곧 시작합니다'로 표기합니다.
                    const h = Math.floor(diff / (1000 * 60 * 60));
                    const m = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                    const s = Math.floor((diff % (1000 * 60)) / 1000);
                    const pad = (n) => String(n).padStart(2, '0');
                    numEl.style.fontSize = '30px';
                    numEl.innerText = pad(h) + ':' + pad(m) + ':' + pad(s);
                    subEl.innerText = '곧 시작합니다!';
                }} else {{
                    // 24시간 이상: 남은 일수
                    // ceil을 사용해 '하루하고 조금 더' 남았을 때 실제 남은 날짜 수(예: 2일)에
                    // 맞춰 표시합니다(floor를 쓰면 1일로 한 칸 낮게 표시되는 오차가 생깁니다).
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


# ----------------------------------------------------------------------
# DB 오류 처리 헬퍼
#   기존 코드는 profile_exists_by_student_no / get_staff_code_info 등
#   "로그인 전"에 호출되는 함수들에 try/except가 전혀 없었습니다.
#   그래서 Supabase 쪽에서 어떤 오류가 나든(예: RLS 정책 무한 재귀,
#   네트워크 오류 등) Streamlit이 처리하지 못한 예외를 그대로 화면에
#   빨간 트레이스백으로 뿌리면서 앱 전체가 멈춰버렸습니다.
#   여기서는 흔한 원인(RLS 무한 재귀)을 알아보기 쉬운 문구로 바꿔주고,
#   st.error + st.stop()으로 "죽지 않고 안내만 보여주는" 형태로 바꿉니다.
# ----------------------------------------------------------------------
def _friendly_db_error(e: Exception) -> str:
    msg = str(e)
    if "infinite recursion detected in policy" in msg or "42P17" in msg:
        return (
            "Supabase의 RLS(행 수준 보안) 정책이 자기 자신을 참조해서 "
            "무한 재귀에 빠졌습니다 (42P17). Supabase 대시보드 SQL Editor에서 "
            "제공받은 RLS 수정 스크립트(fix_rls_recursion_v2.sql)를 실행한 뒤 "
            "다시 시도해주세요."
        )
    return f"데이터베이스 오류가 발생했습니다: {msg}"


# ---------- 학생 로그인/가입 ----------
# 최초 1회: 학번(학교아이디)+이름+학교이메일 → 학교이메일로 받은 인증코드 확인 → 비밀번호 생성
# 이후: 학번 + 비밀번호로 로그인 (내부적으로 저장된 학교이메일 + 비밀번호로 Supabase Auth 로그인)
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
    """학교 이메일로 인증코드(OTP)를 발송합니다. Supabase 이메일 템플릿에 {{ .Token }} 이
    포함되어 있어야 링크가 아닌 6자리 코드가 전송됩니다."""
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
    """verify_student_otp 로 세션이 확보된 상태에서 비밀번호를 설정하고 프로필을 생성합니다."""
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

    # profiles insert는 서비스 키(RLS 우회)로 처리. 서비스 키가 없으면 기존 방식으로 폴백.
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
    # 새로고침 후에도 로그인이 유지되도록 세션 토큰을 쿠키에 저장합니다.
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
    # 새로고침 후에도 로그인이 유지되도록 세션 토큰을 쿠키에 저장합니다.
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


def staff_signup(code: str, name: str, password: str):
    client = get_user_client()
    try:
        auth_res = client.auth.sign_up(
            {"email": staff_email(code), "password": password}
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

    # profiles insert / staff_codes update 모두 서비스 키(RLS 우회)로 처리.
    admin_client = get_admin_client()
    insert_client = admin_client if admin_client is not None else client
    try:
        insert_client.table("profiles").insert({
            "id": user.id,
            "staff_code": code,
            "name": name,
            "identity": "교직원",
            "is_admin": False,
        }).execute()
        # 코드를 "사용됨"으로 표시 (RLS: used_by가 비어있는 코드만 본인 id로 갱신 가능)
        insert_client.table("staff_codes").update({"used_by": user.id}).eq("code", code).execute()
    except Exception as e:
        return False, f"프로필 저장에 실패했습니다: {e}"
    ss.current_user_id = user.id
    ss.profile_cache = None
    # 새로고침 후에도 로그인이 유지되도록 세션 토큰을 쿠키에 저장합니다.
    save_auth_cookies(auth_res.session)
    return True, "계정이 생성되고 로그인되었습니다."


def staff_signin(code: str, password: str):
    client = get_user_client()
    try:
        auth_res = client.auth.sign_in_with_password(
            {"email": staff_email(code), "password": password}
        )
    except Exception:
        return False, "인증코드 또는 비밀번호가 올바르지 않습니다."
    if auth_res.user is None:
        return False, "인증코드 또는 비밀번호가 올바르지 않습니다."
    ss.current_user_id = auth_res.user.id
    ss.profile_cache = None
    # 새로고침 후에도 로그인이 유지되도록 세션 토큰을 쿠키에 저장합니다.
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

# 페이지명 -> 슬러그 (bk-card-btn 링크 생성에 사용)
SLUG_BY_NAME = {name: slug for (name, icon, slug) in PUBLIC_PAGES}

NAV_SLUGS = {slug: name for (name, icon, slug) in PUBLIC_PAGES}
NAV_SLUGS.update({"login": "로그인", "mypage": "마이페이지", "admin": "관리자 페이지", "logout": "__logout__"})


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
        active = " bk-active" if ss.page == name else ""
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
        <div class="bk-brand">🏫 {FESTIVAL_NAME}</div>
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
                <div class="eyebrow">2025 경복고등학교</div>
                <h1>{FESTIVAL_NAME}</h1>
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

    # --------------------------------------------------------------
    # 주요 메뉴 카드 (축제 안내 / 프로그램 / 시간표)
    # 카드 하나당 "한 번의 st.markdown 호출"로 렌더링합니다.
    # (여러 호출에 걸쳐 div를 열고/닫으면 서로 감싸지지 않아
    #  배경 카드만 빈 채로 렌더링되는 문제가 있었습니다.)
    # 이동 버튼은 st.button 대신 ?nav=슬러그 앵커 링크(bk-card-btn)로 처리합니다.
    # --------------------------------------------------------------
    st.markdown('<div class="bk-section-title">주요 메뉴</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)

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

    with c2:
        program_items_html = "".join(
            f"<div style='padding:6px 0;border-bottom:1px solid #EEF0F5;font-size:13px;'>"
            f"{p['icon']} <b>{p['name']}</b><br>"
            f"<span style='color:{MUTED};'>{p['date']} {p['time']} / {p['place']}</span></div>"
            for p in ss.programs[:3]
        )
        st.markdown(
            f"""
            <div class="bk-card">
                <h4>🎤 프로그램</h4>
                {program_items_html}
                <a class="bk-card-btn" href="?nav={SLUG_BY_NAME['프로그램']}" target="_self">전체 프로그램 보기 →</a>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        first_day = list(ss.schedule.keys())[0]
        schedule_items_html = "".join(
            f"<div style='padding:6px 0;border-bottom:1px solid #EEF0F5;font-size:13px;'>"
            f"<b>{it['time']}</b>&nbsp;&nbsp;{it['program']} "
            f"<span style='color:{MUTED};'>({it['place']})</span></div>"
            for it in ss.schedule[first_day][:4]
        )
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
    for n in ss.notices[:4]:
        badge = "<span class='bk-badge-new'>NEW</span>" if n.get("new") else ""
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #EEF0F5;'>"
            f"<div>{n['title']}{badge}</div><div style='color:{MUTED};font-size:13px;'>{n['date']}</div></div>",
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="bk-section-title">🏪 부스 정보</div>', unsafe_allow_html=True)
    bcols = st.columns(4)
    for col, b in zip(bcols, ss.booths):
        with col:
            st.markdown(
                f"""
                <div class="bk-card" style="text-align:center;">
                    <div style="font-size:30px;">{b['icon']}</div>
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
# 페이지 : 프로그램
# ----------------------------------------------------------------------
def page_programs():
    st.markdown('<div class="bk-section-title">🎤 프로그램</div>', unsafe_allow_html=True)
    categories = ["전체", "공연", "체험", "전시", "기타"]
    cat = st.radio("카테고리", categories, horizontal=True, label_visibility="collapsed")
    st.markdown('<div class="bk-card">', unsafe_allow_html=True)

    filtered = ss.programs if cat == "전체" else [p for p in ss.programs if p["category"] == cat]
    if not filtered:
        st.info("해당 카테고리의 프로그램이 없습니다.")
    for p in filtered:
        with st.expander(f"{p['icon']}  {p['name']}  ·  {p['date']} {p['time']}  ·  {p['place']}"):
            st.markdown(f"<span class='bk-chip'>{p['category']}</span>", unsafe_allow_html=True)
            st.write(p["desc"])
    st.markdown('</div>', unsafe_allow_html=True)
    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 시간표
# ----------------------------------------------------------------------
def page_schedule():
    st.markdown('<div class="bk-section-title">📅 시간표</div>', unsafe_allow_html=True)
    st.caption("로그인 없이 누구나 확인할 수 있습니다.")
    st.markdown('<div class="bk-card">', unsafe_allow_html=True)

    days = list(ss.schedule.keys())
    tabs = st.tabs(days)
    for tab, day in zip(tabs, days):
        with tab:
            for it in ss.schedule[day]:
                st.markdown(
                    f"<div style='padding:8px 0;border-bottom:1px solid #EEF0F5;'>"
                    f"<span class='bk-pill'>{it['time']}</span>&nbsp;&nbsp;"
                    f"<b>{it['program']}</b> <span style='color:{MUTED};'>({it['place']})</span></div>",
                    unsafe_allow_html=True,
                )
    st.markdown('</div>', unsafe_allow_html=True)

    lines = []
    for day, items in ss.schedule.items():
        lines.append(f"[{day}]")
        for it in items:
            lines.append(f"{it['time']}  {it['program']}  ({it['place']})")
        lines.append("")
    st.download_button("⬇️ 전체 시간표 다운로드", data="\n".join(lines),
                        file_name="북악제_시간표.txt", mime="text/plain")
    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 부스 정보
# ----------------------------------------------------------------------
def page_booths():
    st.markdown('<div class="bk-section-title">🏪 부스 정보</div>', unsafe_allow_html=True)
    st.caption("부스 신청 기능은 제공하지 않으며, 운영 부스 정보만 안내합니다. (갤러리 기능 없음)")

    cols = st.columns(2)
    for i, b in enumerate(ss.booths):
        with cols[i % 2]:
            st.markdown(
                f"""
                <div class="bk-card" style="margin-bottom:16px;">
                    <div style="font-size:34px;">{b['icon']}</div>
                    <div style="font-weight:800;font-size:17px;margin-top:4px;">{b['name']} <span class="bk-chip">{b['category']}</span></div>
                    <div style="color:{MUTED};margin-top:6px;">📍 {b['place']} &nbsp;|&nbsp; 🕒 {b['hours']}</div>
                    <div style="margin-top:8px;">{b['desc']}</div>
                </div>
                """, unsafe_allow_html=True,
            )
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
    st.markdown('<div class="bk-card">', unsafe_allow_html=True)
    for n in sorted(ss.notices, key=lambda x: x["date"], reverse=True):
        badge = "<span class='bk-badge-new'>NEW</span>" if n.get("new") else ""
        with st.expander(f"{n['title']}   ({n['date']})"):
            st.markdown(badge, unsafe_allow_html=True)
            st.write(n["content"])
    st.markdown('</div>', unsafe_allow_html=True)
    render_footer()


# ----------------------------------------------------------------------
# 페이지 : 로그인 / 인증  (학번·인증코드 + 비밀번호, Supabase Auth)
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

    # ---------------- 학생 ----------------
    # 최초 1회: 학번+이름 → 학교이메일로 인증코드 받기 → 코드 확인 → 비밀번호 생성
    # 이후: 학번 + 비밀번호로 로그인
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

    # ---------------- 교직원 ----------------
    with tab2:
        if ss.staff_step == "check":
            st.caption("미리 발급된 교직원 인증코드를 입력해주세요.")
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
                else:
                    ss.pending_staff_code = code
                    ss.staff_step = "password_existing" if info["used_by"] else "password_new"
                    st.rerun()

        elif ss.staff_step == "password_new":
            st.success(f"인증코드 **{ss.pending_staff_code}**는 처음 사용됩니다. 이름과 비밀번호를 입력해주세요.")
            with st.form("staff_signup_form"):
                s_name = st.text_input("이름")
                pw1 = st.text_input("비밀번호 (6자 이상)", type="password")
                pw2 = st.text_input("비밀번호 확인", type="password")
                c1, c2 = st.columns(2)
                submit = c1.form_submit_button("계정 생성 및 로그인", use_container_width=True)
                back = c2.form_submit_button("← 뒤로", use_container_width=True)
            if back:
                reset_login_steps(); st.rerun()
            if submit:
                if not s_name:
                    st.error("이름을 입력해주세요.")
                elif len(pw1) < 6:
                    st.error("비밀번호는 6자 이상이어야 합니다.")
                elif pw1 != pw2:
                    st.error("비밀번호가 서로 일치하지 않습니다.")
                else:
                    ok, msg = staff_signup(ss.pending_staff_code, s_name.strip(), pw1)
                    if ok:
                        reset_login_steps()
                        st.success(msg)
                        go("마이페이지"); st.rerun()
                    else:
                        st.error(msg)

        elif ss.staff_step == "password_existing":
            st.write(f"인증코드 **{ss.pending_staff_code}** 계정의 비밀번호를 입력해주세요.")
            with st.form("staff_signin_form"):
                pw = st.text_input("비밀번호", type="password")
                c1, c2 = st.columns(2)
                submit = c1.form_submit_button("로그인", use_container_width=True)
                back = c2.form_submit_button("← 뒤로", use_container_width=True)
            if back:
                reset_login_steps(); st.rerun()
            if submit:
                ok, msg = staff_signin(ss.pending_staff_code, pw)
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
            # 로그인(=Auth 세션)은 되어 있는데 profiles 조회에 실패한 경우.
            # "로그인이 필요합니다"라고 하면 원인 파악이 어려우므로 구분해서 보여줍니다.
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
    id_line = f"학번 {user['student_no']}" if user.get("student_no") else f"인증코드 {user.get('staff_code','-')}"
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
        st.warning("`secrets.toml` 에 `SUPABASE_SERVICE_KEY` 가 없어 일부 관리 기능(권한 부여/회수, 인증코드 발급)이 비활성화되어 있습니다.")

    tabs = st.tabs(["🧑‍💻 사용자 관리", "🔑 권한 관리", "🔒 인증코드 관리", "🛠️ 사이트 관리"])

    with tabs[0]:
        st.markdown('<div class="bk-card">', unsafe_allow_html=True)
        st.subheader("사용자 목록")
        client = get_user_client()
        try:
            res = client.table("profiles").select("id,name,identity,is_admin,student_no,staff_code").execute()
            users = res.data or []
        except Exception as e:
            st.error(_friendly_db_error(e))
            users = []
        if not users:
            st.info("등록된 사용자가 없습니다.")
        else:
            rows = [{"ID": u["id"], "이름": u["name"], "신분": u["identity"],
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
        rows = [{"인증코드": c["code"], "상태": "활성" if c["active"] else "비활성",
                 "사용여부": "사용됨" if c["used_by"] else "미사용"} for c in codes]
        st.dataframe(rows, use_container_width=True)

        if admin_client is None:
            st.info("SUPABASE_SERVICE_KEY가 설정되면 인증코드 발급/비활성화를 사용할 수 있습니다.")
        else:
            import random, string
            if st.button("➕ 새 인증코드 생성"):
                new_code = "BK26-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
                admin_client.table("staff_codes").insert({"code": new_code, "active": True}).execute()
                st.success(f"새 인증코드: {new_code}"); st.rerun()
            if codes:
                target_code = st.selectbox("비활성화할 인증코드", ["선택 안함"] + [c["code"] for c in codes])
                if target_code != "선택 안함" and st.button("인증코드 비활성화"):
                    admin_client.table("staff_codes").update({"active": False}).eq("code", target_code).execute()
                    st.success("비활성화했습니다."); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with tabs[3]:
        st.markdown('<div class="bk-card">', unsafe_allow_html=True)
        st.subheader("공지사항 등록")
        with st.form("add_notice_form"):
            t = st.text_input("제목")
            c = st.text_area("내용")
            if st.form_submit_button("공지 등록") and t:
                ss.notices.insert(0, {"title": t, "content": c,
                                       "date": datetime.now().strftime("%Y-%m-%d"), "new": True})
                st.success("공지사항이 등록되었습니다."); st.rerun()

        st.markdown("---")
        st.subheader("부스 등록")
        with st.form("add_booth_form"):
            bn = st.text_input("부스 이름")
            bc = st.text_input("카테고리 (예: 음식/게임/체험/전시)")
            bp = st.text_input("위치")
            bh = st.text_input("운영시간")
            bd = st.text_area("설명")
            if st.form_submit_button("부스 등록") and bn:
                ss.booths.append({"name": bn, "category": bc, "place": bp,
                                   "hours": bh, "desc": bd, "icon": "🏪"})
                st.success("부스가 등록되었습니다."); st.rerun()

        st.markdown("---")
        st.subheader("사이트 기본 정보 수정")
        with st.form("edit_site_info_form"):
            addr = st.text_input("주소", value=ss.site_info["address"])
            subway = st.text_input("지하철 안내", value=ss.site_info["subway"])
            bus = st.text_input("버스 안내", value=ss.site_info["bus"])
            phone = st.text_input("문의 전화", value=ss.site_info["phone"])
            email = st.text_input("이메일", value=ss.site_info["email"])
            if st.form_submit_button("저장"):
                ss.site_info.update({"address": addr, "subway": subway, "bus": bus,
                                      "phone": phone, "email": email})
                st.success("저장되었습니다."); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="bk-section-title">🗂️ 권한별 기능 요약</div>', unsafe_allow_html=True)
    st.markdown('<div class="bk-card">', unsafe_allow_html=True)
    perm_rows = [
        {"기능": "메인 / 축제안내 / 프로그램 / 시간표 / 부스정보 / 오시는길 / 공지사항",
         "비회원": "✅", "학생": "✅", "교직원": "✅", "관리자": "✅"},
        {"기능": "마이페이지", "비회원": "❌", "학생": "✅", "교직원": "✅", "관리자": "✅"},
        {"기능": "관리자 페이지 / 사용자·권한·인증코드·사이트 관리", "비회원": "❌", "학생": "❌", "교직원": "❌", "관리자": "✅"},
        {"기능": "갤러리 / 부스 신청", "비회원": "❌", "학생": "❌", "교직원": "❌", "관리자": "❌"},
    ]
    st.table(perm_rows)
    st.markdown('</div>', unsafe_allow_html=True)
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
    handle_nav_query_param()
    render_topbar_and_drawer()

    routes = {
        "메인": page_main, "축제 안내": page_intro, "프로그램": page_programs,
        "시간표": page_schedule, "부스 정보": page_booths, "오시는 길": page_directions,
        "공지사항": page_notices, "로그인": page_login,
        "마이페이지": page_mypage, "관리자 페이지": page_admin,
    }

    if ss.page == "마이페이지" and current_user() is None and not ss.get("current_user_id"):
        # 진짜 로그인이 안 된 경우만 여기서 막습니다.
        # 로그인은 되어 있는데 프로필 조회만 실패한 경우는 page_mypage() 안에서
        # 원인을 구분해서 보여주도록 통과시킵니다.
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
