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
    "iVBORw0KGgoAAAANSUhEUgAAAdIAAAHRCAYAAADe9DiYAAAQAElEQVR4AexdB4AbxdV+b1V2AVNC6L2E0Ak1QEjAlNBt7Dut6RhJNoZQEiCBhGpaQgo9/Injk2TTAl6dbVroYEIJgRB6S0invsc4/Tqd/HN9zH2t9dU9O/dSbne/dvd7X/vem/nmzbf6/wEAAP//AwBaWKV2gX8/OAAAAABJRU5ErkJggg=="
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
    page_icon=LOGO_IMAGE,
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
