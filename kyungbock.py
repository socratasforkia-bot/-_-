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
(부스도 마찬가지로 등록만 가능했지만, 이번 요청은 공지사항 기준이라
 공지사항 부분만 수정/삭제 기능을 추가했습니다.)

해결: page_admin() 의 "사이트 관리" 탭에 "공지사항 관리" 섹션을 추가했습니다.
    - 등록된 공지사항을 expander로 나열
    - expander를 열면 제목/내용/NEW표시를 수정할 수 있는 폼이 나타나고,
      "수정 저장" 버튼으로 해당 공지사항(ss.notices[idx])을 바로 갱신
    - "🗑️ 삭제" 버튼으로 해당 공지사항을 목록에서 제거(ss.notices.pop(idx))
    - 기존 "공지사항 등록" 폼은 그대로 아래에 유지

----------------------------------------------------------------------
[수정 사항 4 - 공지사항 / 부스 정보가 메인 화면에 반영되지 않던 문제 해결]
기존에는 공지사항과 부스 정보를 st.session_state(ss.notices, ss.booths)라는
"인메모리(브라우저 세션 한정)" 리스트에만 저장했습니다. Streamlit의
session_state는 사용자(브라우저 탭)마다 완전히 분리되어 있고 서버가
재시작되면 초기화되는 임시 저장소입니다. 그래서 관리자가 공지사항/부스를
등록해도 그건 "관리자 자신의 세션"에만 반영될 뿐, 다른 방문자가 메인
페이지를 열었을 때는 전혀 보이지 않았습니다.

해결: 공지사항(notices)과 부스(booths)를 Supabase 테이블로 옮기고,
페이지를 그릴 때마다 fetch_notices() / fetch_booths() 로 DB에서 직접
읽어오도록 바꿨습니다. 등록/수정/삭제도 모두 Supabase에 반영되므로
이제 모든 방문자가 동일한 공지사항/부스 정보를 보게 됩니다.

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

    (등록/수정/삭제는 SUPABASE_SERVICE_KEY로 RLS를 우회해 처리하므로
     별도의 insert/update/delete 정책은 필요 없습니다. 단, secrets.toml에
     SUPABASE_SERVICE_KEY가 없으면 이 기능들은 동작하지 않습니다.)
----------------------------------------------------------------------

[수정 사항 5 - 사이드바(드로어)에서 '메인' 항목 제거 + 헤더 클릭 시 메인 이동]
왼쪽 상단 로고("🏫 북악제")를 클릭하면 메인 페이지로 이동하는 것이 이미
자연스러운 동선이므로, 오른쪽 드로어 메뉴에서는 '메인' 항목을 뺐습니다.
render_topbar_and_drawer()에서 PUBLIC_PAGES를 순회할 때 이름이 "메인"인
항목은 건너뛰고, bk-brand(로고) 부분을 <div>에서 <a href="?nav=home">로
바꿔 클릭 시 메인으로 이동하도록 했습니다.
----------------------------------------------------------------------

[수정 사항 6 - 교직원 로그인 방식 변경: 코드에 사전 등록된 이름 + 아이디/비밀번호]
기존에는 교직원이 인증코드를 입력한 뒤 "본인이 직접" 이름을 타이핑해서
계정을 만들고, 이후에도 계속 "코드+비밀번호"로 로그인해야 했습니다.
요청에 따라 다음과 같이 바꿨습니다.

    1) 관리자가 인증코드를 발급할 때 담당 선생님 "이름"도 함께 입력합니다
       (staff_codes.name 컬럼). 그래서 선생님이 그 코드로 최초 등록할 때는
       이름을 직접 입력하지 않고, 코드에 미리 저장된 이름이 자동으로
       화면에 표시되고 그대로 프로필 이름으로 저장됩니다.
    2) 선생님은 최초 등록 시 코드 확인 후 "아이디(로그인 ID)"와
       "비밀번호"를 새로 만듭니다. 이 아이디+비밀번호 조합으로
       Supabase Auth 계정(가짜 이메일: staffid-아이디@내부도메인)을 만듭니다.
    3) 이후 로그인은 더 이상 "인증코드"가 아니라 "아이디+비밀번호"로 합니다.
       (인증코드는 최초 1회, 본인 확인 및 이름 매칭 용도로만 사용됩니다.)

DB 준비 (추가 SQL, Supabase SQL Editor에서 한 번 실행):

    alter table staff_codes add column if not exists name text;
    alter table profiles add column if not exists staff_username text unique;

    (기존에 이미 등록된 교직원 계정이 있다면, staff_username이 비어있는 동안은
     예전 방식의 "코드+비밀번호" 로그인이 통하지 않게 되므로, 필요하다면
     관리자가 새 인증코드를 재발급해 다시 등록하도록 안내해주세요.)
----------------------------------------------------------------------

[수정 사항 7 - 부스 사진 + 아이콘 함께 표시]
기존에는 부스에 사진을 등록하면 아이콘(이모티콘)은 화면에서 아예 보이지
않고 사진만 표시됐습니다. 요청에 따라 사진이 있어도 아이콘이 사진 위
모서리에 작은 배지 형태로 함께 보이도록 booth_media_html()을 수정했습니다.

----------------------------------------------------------------------
[수정 사항 8 - 공지사항/부스 목록 캐싱으로 체감 속도 개선 + DB 요청 절감]
기존에는 메인 화면을 포함한 모든 페이지 렌더링마다 fetch_notices()/
fetch_booths()가 매번 Supabase에 새로 요청을 보냈습니다. 방문자가 많아질수록
(예: 축제 당일 수백~수천 명이 메인 화면을 새로고침) 완전히 동일한 데이터를
반복해서 DB에 요청하게 되어 불필요하게 느려지고 DB 부하도 커집니다.

해결: fetch_notices()/fetch_booths()에 @st.cache_data(ttl=...)를 적용해
짧은 시간(각각 20초/30초) 동안은 캐시된 결과를 재사용하도록 했습니다.
관리자가 등록/수정/삭제를 하면 즉시 .clear()로 캐시를 비워서, 관리자
본인 화면에는 변경사항이 바로 반영되고, 그 외 방문자에게는 캐시 주기
이내에 반영됩니다. (자세한 설명은 답변 텍스트를 참고하세요.)
----------------------------------------------------------------------
"""

import streamlit as st
import streamlit.components.v1 as components
import base64
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

# 학번/아이디로 만드는 가짜 이메일 도메인 (Supabase Auth 내부용, 실제 발송 안 됨)
FAKE_EMAIL_DOMAIN = "bukakje.internal"

# 공지사항/부스 목록 캐시 유지 시간(초). 방문자가 많을 때 DB 요청을 줄여
# 체감 속도를 높이기 위한 값입니다. 값을 늘리면 DB 부하는 더 줄지만
# 반영 지연은 늘어납니다.
NOTICES_CACHE_TTL = 20
BOOTHS_CACHE_TTL = 30

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
    """서비스 역할 키 클라이언트. RLS를 우회하므로 관리자 기능에서만 사용합니다.
    @st.cache_resource로 앱 전체에서 단 하나의 클라이언트 인스턴스를 재사용합니다
    (요청마다 새로 만들지 않음 → 연결/초기화 비용 절감)."""
    if not SUPABASE_SERVICE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def student_email(student_no: str) -> str:
    return f"student-{student_no.strip()}@{FAKE_EMAIL_DOMAIN}"


def staff_login_email(username: str) -> str:
    """교직원 로그인 아이디로 Supabase Auth용 가짜 이메일을 만듭니다.
    실제로 메일이 발송되지 않는 내부 전용 주소입니다."""
    return f"staffid-{username.strip()}@{FAKE_EMAIL_DOMAIN}"


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
    cursor: pointer;
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
# 세션 상태 초기화 (프로그램/시간표/사이트정보는 데모용 인메모리 유지)
#  - 로그인/사용자/권한 관련 정보는 Supabase로 이동했습니다.
#  - 공지사항(notices)/부스(booths)도 Supabase 테이블로 이동했습니다.
#    (더 이상 ss.notices / ss.booths 를 쓰지 않고, 필요할 때마다
#     fetch_notices() / fetch_booths() 로 DB에서 직접 읽어옵니다.)
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
        ss.staff_step = "check"     # check -> account_new (최초 등록용, 코드 확인 단계)

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
    for k in ("pending_student_no", "pending_student_name", "pending_student_email",
              "pending_staff_code", "pending_staff_name"):
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


# ----------------------------------------------------------------------
# 공지사항 / 부스 — Supabase 연동 (모든 방문자에게 공통으로 보이도록)
#   등록/수정/삭제는 서비스 키(SUPABASE_SERVICE_KEY)로 RLS를 우회해서
#   처리합니다. 서비스 키가 없으면 일반 클라이언트로 시도하되, RLS에
#   막혀 실패할 수 있습니다(그 경우 화면에 오류가 표시됩니다).
#
#   fetch_notices() / fetch_booths() 는 @st.cache_data로 짧게 캐싱합니다.
#   같은 데이터를 모든 방문자가 반복해서 요청하는 상황(예: 축제 당일
#   동시 접속자가 많을 때)에 DB 요청 수를 크게 줄여 체감 속도를 높이기
#   위함입니다. 등록/수정/삭제 직후에는 해당 캐시를 .clear()로 즉시
#   비워서, 변경한 관리자 화면에는 지연 없이 최신 데이터가 보이도록
#   합니다.
# ----------------------------------------------------------------------
def _write_client():
    admin_client = get_admin_client()
    return admin_client if admin_client is not None else get_user_client()


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
# 부스 카드에 쓸 이미지 / 아이콘 영역 HTML
#   - 사진이 있으면: 카드 폭에 꽉 차게, 둥근 모서리 + 그림자를 준
#     비율 유지(object-fit: cover) 박스로 크게 보여주고, 오른쪽 아래에
#     흰 원형 배지로 대표 아이콘(이모티콘)을 함께 표시합니다.
#     (사진과 아이콘을 동시에 볼 수 있도록)
#   - 사진이 없으면: 대표 아이콘(이모티콘)을 큼직하게 그라데이션
#     박스 안에 보여줘서 카드가 휑해 보이지 않게 합니다.
#   메인 페이지 미리보기와 부스 정보 페이지에서 높이만 다르게 주고
#   동일한 스타일을 공유합니다.
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
    if "relation" in msg and "does not exist" in msg:
        return (
            "notices / booths 테이블이 아직 없습니다. 이 파일 상단 주석의 "
            "SQL(create table notices ..., create table booths ...)을 "
            "Supabase SQL Editor에서 먼저 실행해주세요.\n\n"
            f"(원본 오류: {msg})"
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
# 최초 1회: 관리자가 발급한 인증코드 확인 → 코드에 미리 등록된 이름을 그대로 사용
#           → 본인이 원하는 "아이디"와 비밀번호를 새로 생성
# 이후: 아이디 + 비밀번호로 로그인 (더 이상 인증코드를 쓰지 않음)
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
    """인증코드로 본인 확인 후, 코드에 사전 등록된 이름(name)을 그대로 프로필 이름으로
    저장하고, 이후 로그인에 사용할 아이디(username)+비밀번호로 Supabase Auth 계정을
    생성합니다."""
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

    # profiles insert / staff_codes update 모두 서비스 키(RLS 우회)로 처리.
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
        # 코드를 "사용됨"으로 표시 (RLS: used_by가 비어있는 코드만 본인 id로 갱신 가능)
        insert_client.table("staff_codes").update({"used_by": user.id}).eq("code", code).execute()
    except Exception as e:
        return False, f"프로필 저장에 실패했습니다: {e}"
    ss.current_user_id = user.id
    ss.profile_cache = None
    # 새로고침 후에도 로그인이 유지되도록 세션 토큰을 쿠키에 저장합니다.
    save_auth_cookies(auth_res.session)
    return True, "계정이 생성되고 로그인되었습니다."


def staff_signin(username: str, password: str):
    """아이디 + 비밀번호로 로그인합니다 (최초 등록 이후의 일반적인 로그인 방식)."""
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

# 사이드바(드로어) 메뉴에만 노출되는 페이지들.
# PUBLIC_PAGES와 달리 메인 화면 상단 아이콘 메뉴(page_main의 icon_cols)에는
# 넣지 않으므로, 여기에 추가한 페이지는 오직 햄버거 메뉴에서만 보입니다.
DRAWER_ONLY_PAGES = [
    ("인사말", "💌", "greeting"),
]

# 페이지명 -> 슬러그 (bk-card-btn 링크 생성에 사용)
SLUG_BY_NAME = {name: slug for (name, icon, slug) in PUBLIC_PAGES + DRAWER_ONLY_PAGES}

NAV_SLUGS = {slug: name for (name, icon, slug) in PUBLIC_PAGES + DRAWER_ONLY_PAGES}
NAV_SLUGS.update({"login": "로그인", "mypage": "마이페이지", "admin": "관리자 페이지",
                   "booth_add": "부스 등록", "notice_add": "공지사항 등록", "logout": "__logout__"})


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

    # 드로어(사이드) 메뉴에는 '메인'을 넣지 않습니다.
    # 상단 로고("🏫 북악제") 클릭으로 이미 메인으로 이동할 수 있기 때문입니다.
    links_html = ""
    for name, icon, slug in PUBLIC_PAGES:
        if name == "메인":
            continue
        active = " bk-active" if ss.page == name else ""
        links_html += f'<a class="bk-drawer-link{active}" href="?nav={slug}" target="_self">{icon} {name}</a>'

    # 드로어 전용 페이지(예: 인사말)도 같은 방식으로 이어서 렌더링합니다.
    for name, icon, slug in DRAWER_ONLY_PAGES:
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
        <a class="bk-brand" href="?nav=home" target="_self" style="text-decoration:none;">🏫 {FESTIVAL_NAME}</a>
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
    # 주요 메뉴 카드 (축제 안내 / 시간표)
    # 카드 하나당 "한 번의 st.markdown 호출"로 렌더링합니다.
    # (여러 호출에 걸쳐 div를 열고/닫으면 서로 감싸지지 않아
    #  배경 카드만 빈 채로 렌더링되는 문제가 있었습니다.)
    # 이동 버튼은 st.button 대신 ?nav=슬러그 앵커 링크(bk-card-btn)로 처리합니다.
    # (메인 화면에서는 '프로그램' 카드를 뺐습니다. 프로그램 페이지 자체는
    #  햄버거 메뉴/아이콘 메뉴를 통해 그대로 접근할 수 있습니다.)
    # --------------------------------------------------------------
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

    # 공지사항 / 부스 정보는 Supabase에서 매번 새로 읽어와,
    # 관리자가 등록한 내용이 모든 방문자의 메인 화면에 바로 보이게 합니다.
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
# 페이지 : 인사말 (사이드바 전용 - 메인 화면 아이콘 메뉴에는 노출하지 않음)
#   학생회장단 인사말 / 교장선생님 인사말을 탭으로 구분해 보여줍니다.
# ----------------------------------------------------------------------
def page_greeting():
    st.markdown('<div class="bk-section-title">💌 인사말</div>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🎓 학생회장단 인사말", "🏫 교장선생님 인사말"])

    with tab1:
        st.markdown('<div class="bk-card">', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div style="height:120px;border-radius:12px;margin-bottom:16px;
                        background:linear-gradient(135deg,{ORANGE} 0%, {ORANGE_DARK} 100%);
                        display:flex;align-items:center;justify-content:center;color:white;font-size:44px;">
                🎓
            </div>
            """, unsafe_allow_html=True,
        )
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
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="bk-card">', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div style="height:120px;border-radius:12px;margin-bottom:16px;
                        background:linear-gradient(135deg,{NAVY} 0%, {BLUE_PILL} 100%);
                        display:flex;align-items:center;justify-content:center;color:white;font-size:44px;">
                🏫
            </div>
            """, unsafe_allow_html=True,
        )
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

    admin = is_admin()
    booths = fetch_booths()

    if not booths:
        st.info("아직 등록된 부스가 없습니다.")
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

                # ------------------------------------------------------
                # 관리자에게만 보이는 수정/삭제 컨트롤.
                # 카드(bk-card) 자체는 위에서 "한 번의 st.markdown 호출"로
                # 렌더링했으므로, 그 아래에 별도의 expander/form(네이티브
                # 위젯)으로 수정·삭제 기능을 붙입니다.
                # ------------------------------------------------------
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

    # 관리자에게만 보이는 우측 하단 + 버튼 → 부스 등록 페이지로 이동
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
        # fetch_notices()가 이미 최신순(날짜 내림차순)으로 정렬해서 반환합니다.
        for n in notices:
            badge = "<span class='bk-badge-new'>NEW</span>" if n.get("new") else ""
            with st.expander(f"{n['title']}   ({n['date']})"):
                st.markdown(badge, unsafe_allow_html=True)
                st.write(n["content"])

                # ------------------------------------------------------
                # 관리자에게만 보이는 수정/삭제 컨트롤 (부스 정보 페이지와 동일한 방식)
                # ------------------------------------------------------
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

    # 관리자에게만 보이는 우측 하단 + 버튼 → 공지사항 등록 페이지로 이동
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
    # "최초 등록(인증코드)" 과 "로그인(아이디)" 을 하위 탭으로 분리했습니다.
    # 최초 등록 시에는 이름을 직접 입력하지 않고, 관리자가 인증코드 발급 시
    # 미리 입력해 둔 이름을 그대로 사용합니다. 등록이 끝나면 이후에는
    # 인증코드가 아니라 이때 만든 "아이디+비밀번호"로 로그인합니다.
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
        st.warning("`secrets.toml` 에 `SUPABASE_SERVICE_KEY` 가 없어 일부 관리 기능(권한 부여/회수, 인증코드 발급, 공지/부스 등록·수정·삭제)이 비활성화되어 있습니다.")

    tabs = st.tabs(["🧑‍💻 사용자 관리", "🔑 권한 관리", "🔒 인증코드 관리"])

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

        # "담당자(사전 등록)"는 인증코드 발급 시 관리자가 미리 입력한 이름(staff_codes.name)입니다.
        # 코드가 아직 등록에 사용되지 않았어도(=선생님이 아직 로그인 전이어도) 미리 확인할 수 있습니다.
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

    st.caption("📢 공지사항/부스 등록·수정·삭제는 '공지사항', '부스 정보' 메뉴 화면에서 직접 할 수 있습니다 "
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
    handle_nav_query_param()
    render_topbar_and_drawer()

    routes = {
        "메인": page_main, "축제 안내": page_intro, "프로그램": page_programs,
        "시간표": page_schedule, "부스 정보": page_booths, "오시는 길": page_directions,
        "공지사항": page_notices, "인사말": page_greeting, "로그인": page_login,
        "마이페이지": page_mypage, "관리자 페이지": page_admin,
        "부스 등록": page_booth_add, "공지사항 등록": page_notice_add,
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
