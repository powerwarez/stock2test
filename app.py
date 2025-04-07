import os
import streamlit as st
import random
import time
import pandas as pd
from datetime import date
import plotly.express as px
from openai import OpenAI
import json
from supabase import create_client, Client

# --- Streamlit 설정 ---
st.set_page_config(
    page_title="수준별 모의 주식 거래",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS (스타일링) ---
# (기존 CSS 코드는 변경 없이 그대로 사용)
st.markdown(
    """
<style>
/* 전체 폰트 변경 (Nanum Gothic, Google Fonts CDN 사용) */
@import url('https://fonts.googleapis.com/css2?family=Nanum+Gothic:wght@400;700&display=swap');
body {
    font-family: 'Nanum Gothic', sans-serif !important;
}

/* 탭 메뉴 스타일 */
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
    background-color: #007bff !important;
    color: white !important;
    font-weight: bold;
}
.stTabs [data-baseweb="tab-list"] button {
    background-color: #f0f2f6;
    color: #333;
    border-radius: 8px 8px 0 0;
    padding: 0.75em 1em;
    margin-bottom: -1px; /* border overlap */
}

/* 사이드바 스타일 */
[data-testid="stSidebar"] {
    width: 350px !important;
    background-color: #f8f9fa; /* Light gray sidebar background */
    padding: 20px;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h3 {
    color: #212529; /* Dark gray sidebar headings */
}
[data-testid="stSidebar"] hr {
    border-top: 1px solid #e0e0e0; /* Lighter sidebar hr */
}

/* Metric 스타일 */
.streamlit-metric-label {
    font-size: 16px;
    color: #4a4a4a;
}
.streamlit-metric-value {
    font-size: 28px;
    font-weight: bold;
}

/* 버튼 스타일 */
div.stButton > button {
    background-color: #007bff;
    color: white;
    padding: 12px 24px;
    font-size: 16px;
    border-radius: 8px;
    border: none;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.1); /* Soft shadow */
    transition: background-color 0.3s ease;
}
div.stButton > button:hover {
    background-color: #0056b3;
    box-shadow: 2px 2px 7px rgba(0,0,0,0.15); /* Slightly stronger shadow on hover */
}

/* 보조 버튼 스타일 */
div.stButton > button.secondary-button {
    background-color: #6c757d;
    color: white;
    padding: 10px 20px;
    font-size: 14px;
    border-radius: 6px;
    border: none;
    transition: background-color 0.3s ease;
}
div.stButton > button.secondary-button:hover {
    background-color: #5a6268;
}

/* Expander 스타일 */
.streamlit-expanderHeader {
    font-weight: bold;
    color: #212529;
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 8px;
    margin-bottom: 15px;
}

/* Dataframe 스타일 */
.dataframe {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 12px;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.05); /* Very subtle shadow */
}

/* Info, Success, Error, Warning Box 스타일 (더 부드러운 스타일) */
div.stInfo, div.stSuccess, div.stError, div.stWarning {
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 15px;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
}
div.stInfo {
    background-color: #e7f3ff;
    border-left: 5px solid #007bff;
}
div.stSuccess {
    background-color: #e6f7ec;
    border-left: 5px solid #28a745;
}
div.stError {
    background-color: #fdeded;
    border-left: 5px solid #dc3545;
}
div.stWarning {
    background-color: #fffbe6;
    border-left: 5px solid #ffc107;
}

/* Toast message 스타일 */
div.streamlit-toast-container {
    z-index: 10000; /* Toast를 항상 맨 위에 표시 */
}
div[data-testid="stToast"] {
    border-radius: 8px;
    padding: 15px;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
}

</style>
""",
    unsafe_allow_html=True,
)

# --- API 키 설정 ---
if "OPENAI_API_KEY" not in os.environ:
    st.error("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다. API 키를 설정해주세요.")
    st.stop()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# --- Supabase 설정 ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    st.warning("Supabase URL 또는 Key가 설정되지 않았습니다. 데이터 저장/로드가 불가능합니다.")
    supabase = None
else:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Supabase 클라이언트 생성 실패: {e}")
        supabase = None

# --- 수준별 설정 ---
LEVELS = {
    "초등": {"name": "초등 (5~6학년)", "initial_cash": 1_000_000, "grade_level": "초등학생 5~6학년"},
    "중등": {"name": "중등 (1~3학년)", "initial_cash": 5_000_000, "grade_level": "중학생 1~3학년"},
    "고등": {"name": "고등 (1~3학년)", "initial_cash": 10_000_000, "grade_level": "고등학생 1~3학년"},
}

# --- 수준별 주식 설명 ---
# (각 수준에 맞게 설명을 수정하거나 추가)
STOCK_DESCRIPTIONS = {
    "초등": {
        "삼성전자": "TV, 스마트폰 만드는 회사! 갤럭시 알지? 반도체 칩도 세계 최고!",
        "SK하이닉스": "컴퓨터, 스마트폰의 기억력 담당! 사진, 영상 저장 도와줘.",
        "LG디스플레이": "TV, 스마트폰 화면 만드는 회사! OLED 기술로 선명하게!",
        "현대자동차": "자동차 만드는 회사! 쏘나타, 아이오닉 들어봤지? 전기차도 만들어.",
        "기아": "디자인 예쁜 자동차 회사! K5, 쏘렌토, EV6 멋지지?",
        "현대모비스": "자동차 부품 만드는 회사! 엔진, 브레이크 등 안전 부품 담당.",
        "LG에너지솔루션": "전기차 배터리 세계 1등! 미래 에너지 책임져.",
        "SK이노베이션": "기름 만들고, 플라스틱 원료도 만들어. 전기차 배터리도!",
        "두산에너빌리티": "전기 만드는 발전소 짓는 회사! 원자력, 풍력 발전소도.",
        "네이버": "궁금한 거 검색하는 네이버! 뉴스, 웹툰, 쇼핑 다 있어.",
        "카카오": "카카오톡 만든 회사! 택시, 페이, 게임 등 편리한 서비스 가득.",
        "카카오뱅크": "스마트폰 은행! 앱으로 쉽게 돈 보내고 관리해.",
        "CJ제일제당": "맛있는 음식 만드는 회사! 햇반, 비비고 만두 알지?",
        "아모레퍼시픽": "화장품 만드는 회사! 설화수, 이니스프리 들어봤지?",
        "LG생활건강": "샴푸, 치약, 화장품 만드는 회사! 코카콜라도 팔아.",
        "KB금융": "KB국민은행 있는 금융 회사! 돈 관리 도와줘.",
        "신한지주": "신한은행 있는 금융 회사! 카드, 보험도 있어.",
        "하나금융지주": "하나은행 있는 금융 회사! 외국 돈 거래 잘해.",
        "삼성물산": "건물 짓고, 옷도 팔고, 에버랜드도 운영해!",
        "HD현대": "큰 배 만들고, 굴착기 같은 건설 기계도 만들어.",
        "GS건설": "아파트 '자이' 짓는 회사! 살기 좋은 집 만들어.",
        "롯데쇼핑": "롯데백화점, 롯데마트 운영! 쇼핑은 여기서!",
        "이마트": "큰 마트 이마트! 없는 거 빼고 다 있어. 노브랜드 유명해.",
        "KT": "인터넷, 스마트폰 통신 회사! 전화, TV 서비스 제공.",
        "SK텔레콤": "스마트폰 통신 1등 회사! 빠른 5G 서비스 제공.",
        "삼성바이오로직스": "특별한 약(바이오 의약품) 만드는 회사! 아픈 사람 도와줘.",
        "셀트리온": "바이오 의약품 개발하고 만드는 회사! 병 치료 도와줘.",
        "LG화학": "플라스틱, 배터리 만드는 화학 회사! 생활 곳곳에 있어.",
        "금호석유화학": "타이어 원료(합성고무) 만드는 회사! 산업에 꼭 필요해.",
        "POSCO홀딩스": "튼튼한 철 만드는 회사! 자동차, 건물에 쓰여.",
        "현대제철": "자동차, 건물용 철 만드는 회사! 현대차 그룹이야.",
        "대한항공": "비행기 회사! 해외여행 갈 때 타는 비행기.",
        "HMM": "큰 배로 물건 실어 나르는 회사! 수출입 도와줘.",
        "CJ ENM": "tvN, Mnet 방송국 운영! 영화, 음악도 만들어.",
        "하이브": "BTS 소속사! 아이돌 키우고 음악 만들어.",
        "오리온": "초코파이, 포카칩 만드는 과자 회사!",
        "농심": "신라면, 짜파게티 만드는 라면 회사!",
    },
    "중등": { # 중등 수준 설명 (기존 설명 활용 또는 약간 수정)
        "삼성전자": "대한민국 대표 전자 기업. 스마트폰(갤럭시), TV, 가전제품 및 반도체(메모리, 시스템LSI) 생산. 글로벌 시장 점유율 높음.",
        "SK하이닉스": "메모리 반도체(DRAM, NAND Flash) 전문 기업. 데이터센터, PC, 모바일 기기 등에 필수적인 부품 공급.",
        "LG디스플레이": "디스플레이 패널(OLED, LCD) 생산 기업. TV, 스마트폰, 노트북, 차량용 디스플레이 등에 사용. OLED 기술 선도.",
        "현대자동차": "국내 1위, 글로벌 상위권 자동차 제조사. 내연기관차, 전기차(아이오닉), 수소차(넥쏘) 등 다양한 라인업 보유.",
        "기아": "현대차그룹 계열 자동차 제조사. K시리즈, 쏘렌토, 스포티지 등 인기 모델 보유. 디자인 경쟁력 강조 및 전기차(EV) 라인업 확장 중.",
        "현대모비스": "현대차그룹 핵심 부품 계열사. 자동차 모듈, 핵심 부품(전동화, 램프 등), A/S 부품 사업 영위.",
        "LG에너지솔루션": "글로벌 전기차 배터리 시장 선두 기업. 파우치형 배터리 강점. GM, 현대차 등 다수 완성차 업체에 공급.",
        "SK이노베이션": "정유, 석유화학, 윤활유 및 배터리 사업 영위. SK온을 통해 전기차 배터리 사업 확장 중.",
        "두산에너빌리티": "발전 설비(원자력, 화력, 풍력 등) 및 플랜트 건설 전문 기업. 해수담수화, SMR(소형모듈원전), 가스터빈 등 신사업 추진.",
        "네이버": "국내 1위 검색 포털. 검색, 커머스, 핀테크(네이버페이), 콘텐츠(웹툰), 클라우드 등 다양한 인터넷 서비스 제공.",
        "카카오": "국민 메신저 카카오톡 기반 플랫폼 기업. 모빌리티, 페이, 게임, 웹툰, 뱅크 등 다양한 생활 밀착형 서비스 확장.",
        "카카오뱅크": "인터넷 전문 은행. 비대면 금융 서비스 강점. 간편 송금, 대출, 예적금 상품 제공. 플랫폼 기반 성장 추구.",
        "CJ제일제당": "국내 대표 식품 기업. 햇반, 비비고 등 HMR(가정간편식) 강자. 바이오(아미노산 등), 사료 사업도 영위. 글로벌 확장 중.",
        "아모레퍼시픽": "국내 1위 화장품 기업. 설화수, 라네즈, 이니스프리 등 다수 브랜드 보유. 중국 시장 의존도 높았으나 다변화 노력 중.",
        "LG생활건강": "화장품(후, 숨, 오휘), 생활용품(페리오, 엘라스틴), 음료(코카콜라) 사업 영위. 럭셔리 화장품 강점.",
        "KB금융": "국내 리딩 금융지주사. KB국민은행, KB증권, KB손해보험 등 계열사 보유. 은행 중심 안정적 수익 구조.",
        "신한지주": "KB금융과 경쟁하는 리딩 금융지주사. 신한은행, 신한카드, 신한금융투자 등 보유. 비은행 부문 경쟁력 강화 노력.",
        "하나금융지주": "주요 금융지주사 중 하나. 하나은행, 하나증권, 하나카드 등 보유. 외환 및 글로벌 부문 강점.",
        "삼성물산": "삼성그룹 지배구조 핵심. 건설(래미안), 상사, 패션(빈폴), 리조트(에버랜드), 바이오(삼성바이오로직스 지분) 등 다양한 사업 영위.",
        "HD현대": "조선(HD한국조선해양), 건설기계(HD현대인프라코어, HD현대건설기계), 에너지(HD현대오일뱅크) 등 중공업 중심 그룹 지주사.",
        "GS건설": "주택 브랜드 '자이'로 유명한 대형 건설사. 주택, 건축, 플랜트, 인프라 등 다양한 건설 사업 영위.",
        "롯데쇼핑": "롯데그룹 유통 부문 핵심. 백화점, 마트, 슈퍼, 아울렛, 이커머스(롯데ON) 등 운영. 오프라인 채널 강점.",
        "이마트": "신세계그룹 계열 국내 1위 대형마트. 창고형 할인점(트레이더스), 전문점(노브랜드), 온라인(SSG닷컴) 등 운영.",
        "KT": "유무선 통신 서비스 제공. 인터넷, IPTV, 이동통신 등. B2B(클라우드, AI) 및 미디어/콘텐츠 사업 확장 중.",
        "SK텔레콤": "국내 1위 이동통신사. 5G 네트워크 경쟁력. AI, 메타버스, 구독 서비스 등 신성장 동력 발굴.",
        "삼성바이오로직스": "바이오의약품 위탁개발생산(CDMO) 전문 기업. 글로벌 최대 규모 생산 능력 보유. 높은 기술력과 신뢰도 강점.",
        "셀트리온": "바이오시밀러(바이오의약품 복제약) 개발 및 생산 기업. 램시마, 트룩시마 등 글로벌 시장 판매. 신약 개발도 추진.",
        "LG화학": "석유화학, 첨단소재(배터리 소재 등), 생명과학 사업 영위. 배터리 소재 부문 성장성 주목.",
        "금호석유화학": "합성고무(타이어 원료), 합성수지(플라스틱 원료) 주력 화학 기업. 페놀유도체 등 정밀화학 제품도 생산.",
        "POSCO홀딩스": "국내 1위, 글로벌 경쟁력 갖춘 철강 기업 포스코의 지주사. 철강 외 이차전지소재, 수소 등 친환경 미래소재 사업 육성.",
        "현대제철": "현대차그룹 계열 철강사. 자동차 강판, 건설용 형강/철근 등 생산. 전기로 기반 친환경 생산 전환 추진.",
        "대한항공": "국내 1위, FSC(Full Service Carrier) 항공사. 여객 및 화물 운송 사업. 아시아나항공 인수 추진 중.",
        "HMM": "국내 최대 컨테이너 선사. 글로벌 해운 얼라이언스 '디 얼라이언스' 회원사. 해운 시황에 따른 실적 변동성 큼.",
        "CJ ENM": "미디어(tvN, Mnet), 영화(CJ엔터테인먼트), 음악(스톤뮤직), 커머스 사업 영위. 콘텐츠 제작 및 유통 역량 보유.",
        "하이브": "BTS 소속사로 시작한 글로벌 엔터테인먼트 기업. 멀티 레이블 체제. 위버스 플랫폼 기반 팬덤 비즈니스 확장.",
        "오리온": "초코파이로 유명한 제과 기업. 중국, 베트남, 러시아 등 해외 시장 성공적 진출. 간편대용식, 바이오 사업 진출 모색.",
        "농심": "신라면, 짜파게티 등 대표 라면 브랜드 보유. 스낵(새우깡 등), 음료 사업도 영위. 해외 시장, 특히 미국 성장세 주목.",
    },
    "고등": { # 고등 수준 설명 (기존 설명 + 심화 내용)
        "삼성전자": "글로벌 IT 리더. DX(Device eXperience: 스마트폰, 가전)와 DS(Device Solutions: 반도체) 부문 영위. 파운드리 경쟁력 강화 및 AI 반도체 시장 대응 중요.",
        "SK하이닉스": "메모리 반도체 강자. HBM(고대역폭메모리) 등 AI 서버용 고성능 메모리 수요 증가 수혜 기대. NAND 시장 업황 회복 주목.",
        "LG디스플레이": "대형 OLED 시장 주도. IT용 OLED 및 차량용 P-OLED 등 신시장 개척. LCD 사업 축소 및 OLED 전환 가속화.",
        "현대자동차": "글로벌 완성차 업체. 전용 전기차 플랫폼 E-GMP 기반 아이오닉 시리즈 호평. SDV(소프트웨어 중심 자동차) 전환 및 미래 모빌리티(UAM, 로보틱스) 투자 확대.",
        "기아": "현대차그룹 내 디자인 및 EV 특화 브랜드. EV 라인업 성공적 안착. PBV(목적기반모빌리티) 시장 선점 목표.",
        "현대모비스": "자동차 핵심 부품 공급사. 전동화, 자율주행 관련 핵심 기술 내재화 노력. 그룹사 외 수주 확대 및 소프트웨어 역량 강화 필요.",
        "LG에너지솔루션": "글로벌 Top-tier 배터리 셀 제조사. 북미 중심 생산 능력 확대. 원통형, 파우치형, LFP 등 다양한 폼팩터 및 소재 기술 보유. IRA 수혜 기대.",
        "SK이노베이션": "정유/화학 기반 에너지 기업. 배터리 자회사 SK온의 흑자 전환 및 IPO 추진 중요. 카본 투 그린(Carbon to Green) 전략 실행.",
        "두산에너빌리티": "전력 인프라 핵심 기업. 원전 생태계 복원 및 SMR 기술 개발 선도. 가스터빈 국산화 및 수소, 풍력 등 친환경 에너지 포트폴리오 강화.",
        "네이버": "국내 최대 인터넷 플랫폼. 검색 광고, 커머스 중심 안정적 성장. AI(하이퍼클로바X), 클라우드, 웹툰 글로벌 확장 등 미래 성장 동력 확보 노력.",
        "카카오": "모바일 플랫폼 기반 서비스 확장. 카카오톡 채널 및 광고 수익화. 모빌리티, 페이 등 주요 자회사 수익성 개선 및 규제 리스크 관리 중요.",
        "카카오뱅크": "대표적인 인터넷 전문 은행. 중저신용자 대출 확대 및 플랫폼 비즈니스 강화. 금리 환경 변화 및 핀테크 경쟁 심화 대응 필요.",
        "CJ제일제당": "식품(K-Food 글로벌 확산), 바이오(스페셜티 아미노산), F&C(사료) 사업 포트폴리오. 수익성 중심 경영 및 재무구조 개선 노력.",
        "아모레퍼시픽": "화장품 산업 대표 기업. 중국 의존도 축소 및 북미, 유럽 등 신시장 개척. 온라인 채널 강화 및 브랜드 리빌딩 진행 중.",
        "LG생활건강": "화장품, 생활용품, 음료 3개 부문 안정적 사업 구조. 중국 리오프닝 효과 및 북미 사업 성과 주목. 브랜드 포트폴리오 관리 중요.",
        "KB금융": "리딩 금융그룹. 은행의 안정적 이익 기반 위에 비은행(증권, 보험, 카드) 시너지 창출. 디지털 전환 및 비금융 플랫폼 확장 노력.",
        "신한지주": "균형 잡힌 사업 포트폴리오. 비은행 부문 이익 기여도 증대 노력. 글로벌 및 자본시장 부문 경쟁력 강화. 주주환원 정책 확대.",
        "하나금융지주": "은행 중심 금융그룹. 기업금융 및 외환 부문 강점. 비은행 경쟁력 강화 및 디지털 금융 혁신 추진.",
        "삼성물산": "삼성그룹 사실상 지주회사 역할. 보유 지분 가치(삼성전자, 삼성바이오로직스 등) 중요. 건설 수주 및 상사 트레이딩 실적, 신사업(친환경 에너지 등) 성과 주목.",
        "HD현대": "조선 부문 업황 개선 수혜. 건설기계 북미/신흥국 인프라 투자 수혜. 정유 부문 실적 안정화 및 로봇, AI 등 신기술 투자.",
        "GS건설": "주택 시장 변동성 영향. 해외 플랜트 수주 및 신사업(모듈러 주택, 수처리 등) 성과 중요. 재무 건전성 관리 필요.",
        "롯데쇼핑": "백화점, 마트 등 오프라인 유통 강자. 이커머스(롯데ON) 경쟁력 강화 및 수익성 개선 과제. 해외 사업(베트남 등) 성과 주목.",
        "이마트": "오프라인 할인점 경쟁력 유지 및 온라인(SSG닷컴, G마켓) 시너지 창출 노력. SCK컴퍼니(스타벅스) 실적 기여. 수익성 개선 집중.",
        "KT": "통신 본업 안정성 기반 비통신(미디어, 클라우드, AI) 성장 추구. CEO 리스크 해소 후 성장 전략 구체화. 주주환원 정책 유지.",
        "SK텔레콤": "견조한 무선 사업 실적. AI 컴퍼니 전환 목표(에이닷 등). T우주(구독), 이프랜드(메타버스) 등 신사업 성과 가시화 필요.",
        "삼성바이오로직스": "글로벌 CDMO 시장 지배력 강화. 4공장 가동 및 5공장 증설 계획. ADC(항체-약물 접합체) 등 차세대 기술 투자.",
        "셀트리온": "바이오시밀러 퍼스트무버. 미국 시장 직판 체제 구축. 휴미라, 스텔라라 등 블록버스터 바이오시밀러 출시 예정. 신약 개발 역량 강화.",
        "LG화학": "기초소재(석유화학), 첨단소재(양극재 등), 생명과학 사업 영위. LG에너지솔루션 지분 가치 반영. 친환경 소재 및 배터리 소재 집중 육성.",
        "금호석유화학": "합성고무/수지 등 주력 제품 시황 중요. NB라텍스(의료용 장갑 소재) 수요 변화 주목. 주주환원 정책 및 신성장 동력 확보 노력.",
        "POSCO홀딩스": "철강 사업 안정성 및 친환경 전환. 이차전지소재(리튬, 니켈, 양/음극재) 밸류체인 구축 가속화. 수소 사업 비전 제시.",
        "현대제철": "자동차 강판 등 그룹사 물량 기반 안정적 실적. 건설 시황 영향. 탄소중립 목표 달성 위한 수소환원제철 기술 개발 중요.",
        "대한항공": "여객 수요 회복 및 견조한 화물 실적. 유가 및 환율 변동성 영향. 아시아나항공 인수 관련 불확실성 해소 필요.",
        "HMM": "컨테이너 운임 시황 민감. 선대 확장 및 효율화 노력. 매각 이슈 및 글로벌 해운 동맹 재편 영향 주목.",
        "CJ ENM": "방송 광고 시장 둔화 영향. 티빙(OTT) 성장 및 수익성 개선 과제. 피프스시즌(미국 제작사) 등 글로벌 콘텐츠 경쟁력 강화.",
        "하이브": "멀티 레이블 체제 안착 및 신인 그룹 성공적 데뷔. 위버스 플랫폼 수익 모델 다각화. 게임, AI 등 신규 사업 확장.",
        "오리온": "견고한 국내 및 해외(중국, 베트남, 러시아) 실적. 제품 카테고리 확장(간편대용식 등) 및 신규 시장 진출 모색. 바이오 사업 투자.",
        "농심": "국내외 라면 시장 지배력. 해외 법인 고성장 지속. 비용 상승 부담 완화 및 판가 인상 효과. 건강기능식품 등 신사업 추진.",
    }
}

# --- 수준별 용어 사전 ---
GLOSSARY = {
    "초등": {
        "주식": "회사의 작은 조각. 이걸 사면 나도 회사 주인!",
        "주가": "주식 1개의 가격. 사고 싶은 사람이 많으면 오르고, 팔고 싶은 사람이 많으면 내려.",
        "매수": "주식을 사는 것. '나 이 회사 주식 살래!'",
        "매도": "주식을 파는 것. '나 이 주식 팔아서 돈으로 바꿀래!'",
        "포트폴리오": "내가 가진 주식과 현금 꾸러미. 어떤 주식을 얼마나 가졌는지 보여줘.",
        "수익률": "내가 투자한 돈이 얼마나 늘었는지 알려주는 숫자. (%)",
        "상승": "주가가 오르는 것. 기분 좋아!",
        "하락": "주가가 내리는 것. 조금 슬퍼.",
        "변동": "주가가 오르락내리락 춤추는 것.",
        "투자": "돈을 불리기 위해 주식 같은 곳에 돈을 넣는 것.",
        "섹터": "비슷한 일을 하는 회사들 모임. (예: 자동차 회사 모임, 과자 회사 모임)",
        "전일 대비": "어제랑 비교해서 주가가 얼마나 변했는지 보여주는 것.",
        "뉴스": "세상 소식. 회사에 좋은 소식도 있고, 나쁜 소식도 있어.",
        "현금": "내가 지금 바로 쓸 수 있는 돈.",
        "평가액": "내가 가진 주식들을 지금 가격으로 계산하면 얼마인지 알려주는 것.",
        "손익": "내가 돈을 벌었는지(이익), 잃었는지(손해) 알려주는 것.",
    },
    "중등": {
        "주식": "기업이 자금을 모으기 위해 발행하는 소유권 증서. 주주는 회사의 일부를 소유.",
        "주가": "시장에서 거래되는 주식 1주당 가격. 수요와 공급에 따라 결정됨.",
        "매수": "주식을 사는 행위. 가격 상승을 기대하고 구매.",
        "매도": "보유한 주식을 파는 행위. 이익 실현 또는 손실 확정 목적.",
        "포트폴리오": "투자자가 보유한 다양한 자산(주식, 채권, 현금 등)의 구성.",
        "수익률": "투자 원금 대비 발생한 이익의 비율. (총 평가액 - 총 투자금) / 총 투자금 * 100%",
        "상승": "주가가 이전 가격보다 오르는 현상.",
        "하락": "주가가 이전 가격보다 내리는 현상.",
        "변동성": "주가나 시장 지수가 움직이는 정도. 변동성이 크면 가격 변화가 심함.",
        "투자": "미래의 수익을 기대하고 현재의 자금을 투입하는 행위.",
        "섹터": "산업 분류. 비슷한 사업을 영위하는 기업들의 그룹 (예: IT 섹터, 바이오 섹터).",
        "전일 대비 등락률": "오늘 종가가 어제 종가에 비해 얼마나 변동했는지 백분율로 표시.",
        "뉴스 (경제)": "기업 실적, 경제 지표 발표, 정책 변화 등 주가에 영향을 미칠 수 있는 정보.",
        "현금": "즉시 사용 가능한 자금. 포트폴리오 내 유동성 자산.",
        "평가액 (주식)": "보유 주식 수량 × 현재 주가. 포트폴리오의 현재 가치.",
        "손익": "매수 가격과 현재(또는 매도) 가격의 차이로 발생하는 이익 또는 손실.",
        "시가총액": "기업의 전체 주식 가치. 주가 × 총 발행 주식 수.",
        "배당금": "기업이 이익의 일부를 주주에게 나눠주는 돈.",
    },
    "고등": {
        "주식 (보통주)": "기업의 소유권을 나타내는 대표적인 유가증권. 의결권과 배당권 보유.",
        "주가": "자본시장에서 결정되는 주식의 시장 가격. 기업 가치, 업황, 경제 상황 등 복합적 요인 반영.",
        "매수 (Long Position)": "가격 상승을 예상하고 특정 자산을 매입하는 것.",
        "매도 (Short Selling / Position Closing)": "보유 자산을 팔거나(청산), 가격 하락을 예상하고 빌려서 파는 것(공매도).",
        "포트폴리오": "위험 분산 및 수익 극대화를 위해 여러 자산에 분산 투자한 집합.",
        "수익률 (CAGR, 누적)": "투자기간 동안의 연평균 복합 수익률 또는 총 누적 수익률.",
        "상승 (Bull Market)": "주식 시장이 전반적으로 장기간 상승하는 추세.",
        "하락 (Bear Market)": "주식 시장이 전반적으로 장기간 하락하는 추세.",
        "변동성 (Volatility)": "자산 가격의 변동 정도를 나타내는 통계적 지표. 표준편차 등으로 측정.",
        "투자 (Investment)": "자본을 투입하여 미래의 자본 이득이나 소득 증대를 추구하는 행위.",
        "섹터/산업": "경제 활동 영역에 따른 기업 분류 (GICS, KRX 산업분류 등). 경기 순환과의 연관성 분석.",
        "전일 대비 등락률": "기준 시점(주로 전일 종가) 대비 가격 변화율. 시장 모멘텀 파악 지표.",
        "뉴스 (거시/미시)": "금리, 환율, GDP 등 거시경제 지표 및 개별 기업 뉴스(실적, M&A, 신기술 등).",
        "현금 (Cash Equivalents)": "현금 및 단기 금융상품. 포트폴리오의 안정성 및 기회 확보 수단.",
        "평가액 (Mark-to-Market)": "보유 자산을 현재 시장 가격으로 평가한 금액.",
        "손익 (실현/미실현)": "매매를 통해 확정된 손익(실현)과 평가상의 손익(미실현).",
        "시가총액 (Market Capitalization)": "기업의 규모와 시장 가치를 나타내는 지표.",
        "배당수익률": "주가 대비 배당금의 비율. 투자 매력도 판단 지표 중 하나.",
        "PER (주가수익비율)": "주가 / 주당순이익(EPS). 기업의 수익성 대비 주가 수준 평가.",
        "PBR (주가순자산비율)": "주가 / 주당순자산(BPS). 기업의 자산가치 대비 주가 수준 평가.",
        "ROE (자기자본이익률)": "당기순이익 / 자기자본. 기업의 수익성 및 효율성 지표.",
    }
}

# --- 세션 상태 초기화 ---
def initialize_session_state(selected_level):
    level_info = LEVELS[selected_level]
    initial_cash = level_info["initial_cash"]

    # 포트폴리오 초기화 (기존 데이터 없거나 리셋 필요 시)
    if "portfolio" not in st.session_state or st.session_state.get("force_reset"):
        st.session_state["portfolio"] = {"cash": initial_cash, "stocks": {}}
        st.session_state["initial_cash_set"] = initial_cash # 초기 자본금 기록
        if "force_reset" in st.session_state:
            del st.session_state["force_reset"] # 리셋 플래그 제거

    # 주식 정보 초기화 (기존 데이터 없거나 리셋 필요 시)
    if "stocks" not in st.session_state or not st.session_state["stocks"]: # stocks가 비어있을 때도 초기화
        st.session_state["stocks"] = {}
        base_stocks_data = { # 기본 구조만 정의
            "기술(Tech)": ["삼성전자", "SK하이닉스", "LG디스플레이"],
            "자동차(Auto)": ["현대자동차", "기아", "현대모비스"],
            "에너지(Energy)": ["LG에너지솔루션", "SK이노베이션", "두산에너빌리티"],
            "인터넷(Internet)": ["네이버", "카카오", "카카오뱅크"],
            "소비재(Consumer Goods)": ["CJ제일제당", "아모레퍼시픽", "LG생활건강"],
            "금융(Finance)": ["KB금융", "신한지주", "하나금융지주"],
            "건설(Construction)": ["삼성물산", "HD현대", "GS건설"],
            "유통(Retail)": ["롯데쇼핑", "이마트"],
            "통신(Telecom)": ["KT", "SK텔레콤"],
            "제약/바이오(Pharma/Bio)": ["삼성바이오로직스", "셀트리온"],
            "화학(Chemical)": ["LG화학", "금호석유화학"],
            "철강(Steel)": ["POSCO홀딩스", "현대제철"],
            "운송(Transportation)": ["대한항공", "HMM"],
            "엔터테인먼트(Entertainment)": ["CJ ENM", "하이브"],
            "식품(Food)": ["오리온", "농심"],
        }
        # 각 수준별 설명 매핑 및 초기 가격 설정
        for sector, stock_list in base_stocks_data.items():
            st.session_state["stocks"][sector] = {}
            for stock_name in stock_list:
                # 초기 가격 랜덤 설정 (기존 로직 유지, 약간의 조정 가능)
                if stock_name in ["삼성전자", "SK하이닉스", "기아", "KB금융", "신한지주", "HD현대", "GS건설", "KT", "SK텔레콤", "현대제철", "대한항공", "HMM", "카카오", "카카오뱅크"]:
                    price = random.randint(30000, 90000) # 범위 약간 조정
                elif stock_name in ["LG디스플레이", "두산에너빌리티", "하나금융지주"]:
                     price = random.randint(15000, 45000)
                elif stock_name in ["현대자동차", "현대모비스", "SK이노베이션", "네이버", "아모레퍼시픽", "삼성물산", "롯데쇼핑", "이마트", "셀트리온", "금호석유화학", "CJ ENM", "하이브", "오리온"]:
                     price = random.randint(120000, 280000)
                elif stock_name in ["LG에너지솔루션", "CJ제일제당", "POSCO홀딩스", "농심"]:
                     price = random.randint(280000, 450000)
                elif stock_name in ["LG생활건강", "삼성바이오로직스", "LG화학"]:
                     price = random.randint(500000, 800000)
                else:
                     price = random.randint(50000, 150000) # 기본값

                st.session_state["stocks"][sector][stock_name] = {
                    "current_price": price,
                    "price_history": [price], # 초기 가격 기록
                    "description_초등": STOCK_DESCRIPTIONS["초등"].get(stock_name, "설명 없음"),
                    "description_중등": STOCK_DESCRIPTIONS["중등"].get(stock_name, "설명 없음"),
                    "description_고등": STOCK_DESCRIPTIONS["고등"].get(stock_name, "설명 없음"),
                }

    # 나머지 세션 상태 초기화 (기존 로직 유지, 필요시 추가)
    if "chat_session" not in st.session_state: st.session_state["chat_session"] = []
    if "news_analysis_results" not in st.session_state: st.session_state["news_analysis_results"] = {}
    if "messages" not in st.session_state: st.session_state["messages"] = []
    if "daily_news" not in st.session_state: st.session_state["daily_news"] = None
    if "previous_daily_news" not in st.session_state: st.session_state["previous_daily_news"] = None
    # if "news_date" not in st.session_state: st.session_state["news_date"] = None # 날짜 사용 안 함
    if "news_meanings" not in st.session_state: st.session_state["news_meanings"] = {}
    # if "ai_news_analysis_output" not in st.session_state: st.session_state["ai_news_analysis_output"] = {} # 사용 안 함
    if "day_count" not in st.session_state: st.session_state["day_count"] = 1
    if "sector_news_impact" not in st.session_state: st.session_state["sector_news_impact"] = {}
    if 'buy_confirm' not in st.session_state: st.session_state['buy_confirm'] = False
    if 'sell_confirm' not in st.session_state: st.session_state['sell_confirm'] = False
    if 'user_id' not in st.session_state: st.session_state['user_id'] = None
    if 'user_settings' not in st.session_state: st.session_state['user_settings'] = None
    if 'selected_level' not in st.session_state: st.session_state['selected_level'] = "초등" # 기본값

# --- 뉴스 생성 함수 (수준별) ---
def generate_news():
    selected_level = st.session_state.get('selected_level', '초등')
    level_info = LEVELS[selected_level]
    grade_level_text = level_info['grade_level']

    if selected_level == '초등':
        level_instruction = f"{grade_level_text} 수준에 맞춰 아주 쉽고 구체적인 예시(예: 장난감, 과자, 게임)를 들어 설명해주세요. 어려운 경제 용어(예: 금리, 환율, 인플레이션)는 최대한 피하고, 일상 생활과 관련된 내용으로 작성해주세요."
        sentence_count = "8~10문장"
    elif selected_level == '중등':
        level_instruction = f"{grade_level_text} 수준에 맞춰 작성해주세요. 기본적인 경제 개념(예: 수요와 공급, 경쟁, 인기 상품)을 포함해도 좋습니다. 너무 전문적이지 않게 설명해주세요."
        sentence_count = "10~12문장"
    else: # 고등
        level_instruction = f"{grade_level_text} 수준에 맞춰 작성해주세요. 경제 지표(예: 성장률, 실업률), 국제 관계, 기술 트렌드, 금리 변동 등 좀 더 심도 있는 내용을 다루어도 좋습니다. 분석적인 시각을 포함해주세요."
        sentence_count = "12~15문장"

    prompt = f"""
지시:
{level_instruction}
주식 시장과 경제에 관련된 뉴스 기사 5개를 생성해주세요.
각 기사는 {sentence_count} 정도로 자세하게 작성하고, 특정 회사 이름이나 주식 종목을 직접적으로 언급하지 마세요.
학생들이 뉴스를 읽고 어떤 종류의 회사가 유망할지 또는 어려움을 겪을지 스스로 추론할 수 있도록, 일반적인 경제 상황이나 특정 산업(예: IT, 자동차, 게임, 식품, 에너지 등) 동향에 대한 뉴스를 만들어주세요.
긍정적인 뉴스, 부정적인 뉴스, 중립적인 뉴스를 다양하게 포함하되, '긍정적/부정적/중립적'이라는 단어는 뉴스 본문에 쓰지 마세요.
뉴스 내용에 따라 관련 주식들의 가격이 오르거나 내릴 수 있는 단서를 포함해주세요.
각 뉴스 기사는 "## 뉴스 [번호]" 로 시작해주세요. (예: ## 뉴스 1, ## 뉴스 2 ...)

**생성된 뉴스 기사:**
"""
    messages = [{"role": "user", "content": prompt}]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # 또는 gpt-4o
            messages=messages,
            temperature=0.7,
            max_tokens=1500, # 토큰 수 조정 가능
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0
        )
        news_text = response.choices[0].message.content.strip()

        news_articles = []
        if news_text:
            # "## 뉴스 " 기준으로 나누고, 빈 문자열 제거
            raw_articles = news_text.split("## 뉴스 ")
            for article in raw_articles:
                if article.strip():
                    # 뉴스 번호 제거 및 공백 제거
                    content = article.split('\n', 1)[-1].strip() if '\n' in article else article.strip()
                    if content: # 내용이 있는 경우에만 추가
                         # 뉴스 번호 부분 제거 (예: "1\n뉴스 내용..." -> "뉴스 내용...")
                        if content and content[0].isdigit() and content[1:3] in ['\n', '. ']:
                             content = content.split('\n', 1)[-1].strip()
                        news_articles.append(content)

        # 정확히 5개가 생성되지 않았을 경우 처리 (예: 부족하면 빈 문자열 추가, 많으면 자르기)
        if len(news_articles) < 5:
            news_articles.extend(["(뉴스 생성 실패)"] * (5 - len(news_articles)))
        return news_articles[:5]

    except Exception as e:
        st.error(f"뉴스 생성 중 오류 발생: {e}")
        return ["(뉴스 생성 오류)"] * 5


# --- 뉴스 해설 함수 (수준별) ---
def explain_daily_news_meanings(daily_news):
    if daily_news is None:
        return {}

    selected_level = st.session_state.get('selected_level', '초등')
    level_info = LEVELS[selected_level]
    grade_level_text = level_info['grade_level']

    if selected_level == '초등':
        level_instruction = f"{grade_level_text}이 이해하기 쉽게 아주 쉬운 단어로 2~3문장 이내로 요약해주세요. 비유나 쉬운 예시를 사용하면 좋습니다."
    elif selected_level == '중등':
        level_instruction = f"{grade_level_text}이 이해하기 쉽게 핵심 내용을 3문장 정도로 요약해주세요. 관련 경제 용어가 있다면 간단히 설명해주세요."
    else: # 고등
        level_instruction = f"{grade_level_text}이 이해할 수 있도록 핵심 내용과 이 뉴스가 경제나 특정 산업에 미칠 수 있는 잠재적 영향을 3-4문장 정도로 분석적으로 요약해주세요."

    meanings = {}
    valid_sectors_list = list(st.session_state["stocks"].keys()) # 미리 목록 생성

    for i, news_article in enumerate(daily_news):
        if "(뉴스 생성 오류)" in news_article or "(뉴스 생성 실패)" in news_article:
             meanings[str(i + 1)] = {"explanation": "뉴스 생성에 실패하여 해설할 수 없습니다.", "sectors": []}
             continue

        prompt = f"""
**신문 기사:**
{news_article}

**지시:**
위 신문 기사의 핵심 의미를 {level_instruction} "해설: " 다음에 설명해주세요.
그리고 이 뉴스와 가장 관련성이 높은 주식 섹터 1~2개를 쉼표로 구분해서 "관련 섹터: " 다음에 알려주세요. 제시된 섹터 목록 [{', '.join(valid_sectors_list)}] 중에서만 선택하고, 관련 섹터가 명확하지 않거나 없다면 "관련 섹터: 없음" 이라고 해주세요.

뉴스 의미 해설:
"""
        messages = [{"role": "user", "content": prompt}]
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini", # 또는 gpt-4o
                messages=messages,
                temperature=0.5,
                max_tokens=300,
                top_p=0.95,
                frequency_penalty=0,
                presence_penalty=0
            )
            meaning_text = response.choices[0].message.content.strip()

            explanation = ""
            related_sectors = []

            # "해설:" 부분 추출
            if "해설:" in meaning_text:
                explanation_start_index = meaning_text.find("해설:") + len("해설:")
                # "관련 섹터:" 앞까지 또는 문자열 끝까지 추출
                explanation_end_index = meaning_text.find("관련 섹터:")
                if explanation_end_index != -1:
                    explanation = meaning_text[explanation_start_index:explanation_end_index].strip()
                else:
                    explanation = meaning_text[explanation_start_index:].strip()
            else:
                explanation = "AI 해설 생성에 실패했습니다." # 해설 태그가 없는 경우

            # "관련 섹터:" 부분 추출
            if "관련 섹터:" in meaning_text:
                related_sectors_str = meaning_text.split("관련 섹터:")[-1].strip()
                if related_sectors_str.lower() != "없음" and related_sectors_str:
                    # 제시된 섹터 목록과 비교하여 유효한 섹터만 필터링
                    potential_sectors = [sector.strip() for sector in related_sectors_str.split(',')]
                    related_sectors = [s for s in potential_sectors if s in valid_sectors_list] # 미리 생성한 목록 사용
                else:
                    related_sectors = [] # "없음" 또는 빈 문자열인 경우 빈 리스트
            else:
                 related_sectors = [] # 관련 섹터 태그가 없는 경우

            meanings[str(i + 1)] = {"explanation": explanation, "sectors": related_sectors}

        except Exception as e:
            st.error(f"뉴스 {i+1} 해설 중 오류 발생: {e}")
            meanings[str(i + 1)] = {"explanation": f"오류 발생: {e}", "sectors": []}
        time.sleep(0.5) # API 호출 간격
    return meanings

# --- 주식 매수/매도 함수 (기존과 동일, 메시지 처리 강화) ---
def buy_stock(stock_name, quantity, sector):
    if (
        sector not in st.session_state["stocks"]
        or stock_name not in st.session_state["stocks"][sector]
    ):
        st.error("존재하지 않는 주식 종목입니다.")
        st.toast("존재하지 않는 주식 종목입니다.", icon="❌")
        return

    if quantity <= 0:
        st.error("매수 수량은 1주 이상이어야 합니다.")
        st.toast("매수 수량은 1주 이상이어야 합니다.", icon="❌")
        return

    stock_price = st.session_state["stocks"][sector][stock_name]["current_price"]
    total_price = stock_price * quantity

    if st.session_state["portfolio"]["cash"] >= total_price:
        st.session_state["portfolio"]["cash"] -= total_price
        portfolio_stocks = st.session_state["portfolio"]["stocks"]
        if stock_name in portfolio_stocks:
            # 평균 매수 단가 재계산
            current_quantity = portfolio_stocks[stock_name]["quantity"]
            current_total_purchase = portfolio_stocks[stock_name]["purchase_price"] * current_quantity
            new_quantity = current_quantity + quantity
            new_total_purchase = current_total_purchase + total_price
            portfolio_stocks[stock_name]["quantity"] = new_quantity
            portfolio_stocks[stock_name]["purchase_price"] = new_total_purchase / new_quantity if new_quantity > 0 else 0
        else:
            portfolio_stocks[stock_name] = {
                "quantity": quantity,
                "purchase_price": stock_price, # 첫 매수 시 매수 단가는 현재가
            }
        success_msg = f"{stock_name} {quantity}주 매수 완료! (총 {total_price:,.0f}원)"
        st.success(success_msg)
        st.toast(success_msg, icon="✅")
        st.session_state['buy_confirm'] = False # 확인 상태 초기화
        save_session_data() # 상태 저장
    else:
        max_quantity = st.session_state["portfolio"]["cash"] // stock_price if stock_price > 0 else 0
        error_msg = f"잔액 부족! (최대 {max_quantity}주 매수 가능)"
        st.error(error_msg)
        st.toast(error_msg, icon="❌")
        st.session_state['buy_confirm'] = False # 확인 상태 초기화

def sell_stock(stock_name, quantity):
    if stock_name not in st.session_state["portfolio"]["stocks"]:
        st.error("보유하고 있지 않은 주식입니다.")
        st.toast("보유하고 있지 않은 주식입니다.", icon="❌")
        return

    owned_quantity = st.session_state["portfolio"]["stocks"][stock_name]["quantity"]

    if quantity <= 0:
        st.error("매도 수량은 1주 이상이어야 합니다.")
        st.toast("매도 수량은 1주 이상이어야 합니다.", icon="❌")
        return

    if quantity > owned_quantity:
        st.error(f"매도 가능 수량 초과! (최대 {owned_quantity}주 매도 가능)")
        st.toast(f"매도 가능 수량 초과! (최대 {owned_quantity}주 매도 가능)", icon="❌")
        return

    # 현재가 찾기
    stock_price = 0
    stock_sector = ""
    for sector, stocks_in_sector in st.session_state["stocks"].items():
        if stock_name in stocks_in_sector:
            stock_price = stocks_in_sector[stock_name]["current_price"]
            stock_sector = sector
            break

    if stock_price <= 0: # 0 또는 음수 가격 오류 방지
        st.error("주식 가격 정보를 찾을 수 없거나 유효하지 않습니다.")
        st.toast("주식 가격 정보를 찾을 수 없거나 유효하지 않습니다.", icon="❌")
        return

    sell_value = stock_price * quantity
    st.session_state["portfolio"]["cash"] += sell_value
    st.session_state["portfolio"]["stocks"][stock_name]["quantity"] -= quantity

    # 보유 수량이 0이 되면 포트폴리오에서 제거
    if st.session_state["portfolio"]["stocks"][stock_name]["quantity"] == 0:
        del st.session_state["portfolio"]["stocks"][stock_name]

    success_msg = f"{stock_name} {quantity}주 매도 완료! (+{sell_value:,.0f}원)"
    st.success(success_msg)
    st.toast(success_msg, icon="✅")
    st.session_state['sell_confirm'] = False # 확인 상태 초기화
    save_session_data() # 상태 저장

# --- 주가 업데이트 함수 (기존과 유사, 뉴스 영향 반영) ---
def update_stock_prices():
    if not st.session_state.get("news_meanings"): # 뉴스가 아니라 뉴스 해설 기준으로 변경
        # 뉴스가 없으면 랜덤 변동만 적용
        for sector in st.session_state["stocks"]:
            for stock_name in st.session_state["stocks"][sector]:
                change_rate = random.uniform(-0.03, 0.03) # 기본 변동폭
                change_rate = max(-0.1, min(0.1, change_rate)) # 최대 변동폭 제한
                current_price = st.session_state["stocks"][sector][stock_name]["current_price"]
                new_price = current_price * (1 + change_rate)
                new_price = max(1, int(new_price)) # 최소 1원
                st.session_state["stocks"][sector][stock_name]["current_price"] = new_price
                st.session_state["stocks"][sector][stock_name]["price_history"].append(new_price)
        st.info("주가가 임의로 변동되었습니다.")
        st.toast("주가가 임의로 변동되었습니다.", icon="📈")
        st.session_state["sector_news_impact"] = {} # 뉴스 영향 없음
        return

    # 뉴스 해설 기반 섹터 영향 계산
    sector_impacts = {sector: 0.0 for sector in st.session_state["stocks"]}
    news_meanings = st.session_state["news_meanings"]

    for news_index, meaning_data in news_meanings.items():
        explanation = meaning_data.get("explanation", "")
        related_sectors = meaning_data.get("sectors", [])

        # 간단한 감성 분석 (긍정/부정 키워드 기반)
        positive_keywords = ["성장", "증가", "호황", "개발 성공", "수출 증가", "인기", "기대", "긍정적", "개선", "호조", "확대"]
        negative_keywords = ["감소", "하락", "부진", "어려움", "위기", "경쟁 심화", "규제", "부정적", "악화", "축소", "둔화"]

        sentiment_score = 0
        # 설명에서 키워드 빈도 계산 (간단 버전)
        for p_kw in positive_keywords:
            sentiment_score += explanation.count(p_kw)
        for n_kw in negative_keywords:
            sentiment_score -= explanation.count(n_kw)

        # 관련 섹터에 영향 적용 (점수 기반으로 영향력 조절)
        impact_magnitude = 0.0 # 기본 영향력 0
        if sentiment_score > 0:
            impact_magnitude = random.uniform(0.01, 0.04) * min(sentiment_score, 3) # 영향력 상한선 설정
        elif sentiment_score < 0:
            impact_magnitude = random.uniform(-0.04, -0.01) * min(abs(sentiment_score), 3) # 영향력 상한선 설정

        for sector in related_sectors:
            if sector in sector_impacts:
                sector_impacts[sector] += impact_magnitude

    # 개별 주가 업데이트 (기본 변동 + 섹터 영향)
    for sector in st.session_state["stocks"]:
        sector_impact = sector_impacts.get(sector, 0.0)
        for stock_name in st.session_state["stocks"][sector]:
            # 기본 랜덤 변동 (변동폭 약간 줄임)
            random_change = random.uniform(-0.02, 0.02)
            # 총 변동률 = 기본 변동 + 섹터 영향
            total_change_rate = random_change + sector_impact
            # 변동률 제한 (예: 하루 최대 +/- 15%)
            total_change_rate = max(-0.15, min(0.15, total_change_rate))

            current_price = st.session_state["stocks"][sector][stock_name]["current_price"]
            new_price = current_price * (1 + total_change_rate)
            # 가격이 0 이하로 떨어지지 않도록 최소 1원으로 설정
            new_price = max(1, int(new_price))

            st.session_state["stocks"][sector][stock_name]["current_price"] = new_price
            st.session_state["stocks"][sector][stock_name]["price_history"].append(new_price)

    st.info("뉴스 영향을 반영하여 주가가 변동되었습니다.")
    st.toast("주가가 변동되었습니다.", icon="📊")
    st.session_state["sector_news_impact"] = sector_impacts # 디버깅 또는 정보 제공용


# --- 포트폴리오 정보 계산 함수 ---
def calculate_portfolio_summary():
    portfolio = st.session_state.get("portfolio", {"cash": 0, "stocks": {}}) # 기본값 설정
    cash = portfolio.get("cash", 0)
    total_stock_value = 0
    total_purchase_value = 0

    for stock_name, stock_info in portfolio.get("stocks", {}).items():
        quantity = stock_info.get("quantity", 0)
        purchase_price = stock_info.get("purchase_price", 0)
        current_price = 0
        # 현재가 찾기
        for sector, stocks_in_sector in st.session_state.get("stocks", {}).items():
            if stock_name in stocks_in_sector:
                current_price = stocks_in_sector[stock_name].get("current_price", 0)
                break
        if current_price > 0 and quantity > 0:
            total_stock_value += current_price * quantity
            total_purchase_value += purchase_price * quantity

    total_value = cash + total_stock_value
    # 초기 자본금 가져오기 (없으면 현재 레벨 기본값 사용)
    initial_cash = st.session_state.get("initial_cash_set", LEVELS[st.session_state.get('selected_level', '초등')]['initial_cash'])

    total_profit_loss = total_value - initial_cash
    total_profit_rate = (total_profit_loss / initial_cash) * 100 if initial_cash > 0 else 0

    return cash, total_value, total_profit_loss, total_profit_rate, initial_cash

# --- 화면 표시 함수 ---

def display_stock_prices():
    selected_level = st.session_state.get('selected_level', '초등')
    stocks_data = []
    if "stocks" not in st.session_state or not st.session_state["stocks"]:
        st.warning("주식 정보가 로드되지 않았습니다. 앱을 다시 시작하거나 관리자에게 문의하세요.")
        return

    for sector, sector_stocks in st.session_state["stocks"].items():
        for stock_name, stock_info in sector_stocks.items():
            price_history = stock_info.get("price_history", [])
            current_price = stock_info.get("current_price", 0)
            daily_change_rate_str = " - "
            if len(price_history) >= 2:
                previous_day_price = price_history[-2]
                if previous_day_price > 0: # 0으로 나누기 방지
                    daily_change_rate = (current_price - previous_day_price) / previous_day_price * 100
                    daily_change_rate_str = f"{daily_change_rate:+.2f}%" # 부호 표시
                else:
                    daily_change_rate_str = "N/A"

            stocks_data.append(
                {
                    "종목": stock_name,
                    "섹터": sector,
                    "현재 주가": f"{current_price:,.0f} 원",
                    "전일 대비": daily_change_rate_str,
                    "price_history": price_history,
                    # 수준별 설명 가져오기 (키 형식 변경 반영)
                    "description": stock_info.get(f"description_{selected_level}", stock_info.get("description_중등", "설명 없음")),
                }
            )

    if not stocks_data:
        st.info("표시할 주식 데이터가 없습니다.")
        return

    stocks_df = pd.DataFrame(stocks_data)
    # 컬럼 순서 지정 및 표시
    st.dataframe(stocks_df[["섹터", "종목", "현재 주가", "전일 대비"]], hide_index=True, use_container_width=True)

    st.markdown("---")
    # 상세 정보 보기
    stock_names_list = ["종목 선택..."] + stocks_df["종목"].tolist()
    selected_stock_all_info = st.selectbox(
        "종목 상세 정보 보기 (기업 정보 및 주가 그래프)", stock_names_list, key="stock_detail_select"
    )

    if selected_stock_all_info and selected_stock_all_info != "종목 선택...":
        # stocks_df에서 데이터 찾기 (오류 방지)
        selected_stock_data_list = stocks_df[stocks_df["종목"] == selected_stock_all_info]
        if not selected_stock_data_list.empty:
            selected_stock_data = selected_stock_data_list.iloc[0]
            selected_stock_sector = selected_stock_data["섹터"]

            col1_info, col2_graph = st.columns([1, 1]) # 비율 조정

            with col1_info:
                st.subheader(f"🏢 {selected_stock_all_info} ({selected_stock_sector}) 기업 정보")
                # 수준에 맞는 설명 표시
                st.info(f"{selected_stock_data['description']}")

            with col2_graph:
                st.subheader("📈 주가 그래프")
                price_history = selected_stock_data["price_history"]
                if len(price_history) > 1:
                    price_history_df = pd.DataFrame({
                        "날짜": range(1, len(price_history) + 1),
                        "주가": price_history,
                    })
                    fig = px.line(
                        price_history_df, x="날짜", y="주가",
                        labels={'날짜': f'거래일 (Day)', '주가': '주가 (원)'}
                    )
                    fig.update_layout(margin=dict(l=0, r=0, t=30, b=0)) # 여백 최소화
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("주가 기록이 부족하여 그래프를 표시할 수 없습니다.")
        else:
            st.warning(f"'{selected_stock_all_info}' 종목 정보를 찾을 수 없습니다.")


def display_portfolio_table():
    portfolio = st.session_state.get("portfolio", {"cash": 0, "stocks": {}})
    portfolio_stocks = portfolio.get("stocks", {})

    if portfolio_stocks:
        portfolio_data = []
        total_stock_value = 0
        total_purchase_value_all = 0 # 모든 주식의 총 매수 금액 합계

        for stock_name, stock_info in portfolio_stocks.items():
            quantity = stock_info.get("quantity", 0)
            purchase_price = stock_info.get("purchase_price", 0) # 평균 매수 단가
            current_price = 0
            stock_sector = ""
            # 현재가 및 섹터 찾기
            for sector, stocks_in_sector in st.session_state.get("stocks", {}).items():
                if stock_name in stocks_in_sector:
                    current_price = stocks_in_sector[stock_name].get("current_price", 0)
                    stock_sector = sector
                    break

            if current_price <= 0 or quantity <= 0: continue # 유효하지 않은 데이터 건너뛰기

            current_value = current_price * quantity # 현재 평가액
            purchase_value_total = purchase_price * quantity # 총 매수 금액 (이 종목)
            profit_loss = current_value - purchase_value_total # 손익 금액
            profit_rate = (profit_loss / purchase_value_total) * 100 if purchase_value_total > 0 else 0 # 수익률

            total_stock_value += current_value
            total_purchase_value_all += purchase_value_total

            portfolio_data.append({
                "종목": stock_name,
                "섹터": stock_sector,
                "보유 수량": quantity,
                "평균 매수가": f"{purchase_price:,.0f} 원", # 컬럼명 변경
                "현재가": f"{current_price:,.0f} 원",
                "평가액": f"{current_value:,.0f} 원",
                "손익": f"{profit_loss:,.0f} 원",
                "수익률": f"{profit_rate:.2f}%",
            })

        # 현금 행 추가
        portfolio_data.append({
            "종목": "💰 현금", "섹터": "-", "보유 수량": "-", "평균 매수가": "-",
            "현재가": "-", "평가액": f"{portfolio.get('cash', 0):,.0f} 원", "손익": "-", "수익률": "-",
        })

        portfolio_df = pd.DataFrame(portfolio_data)
        # 컬럼 순서 지정 및 표시
        st.dataframe(portfolio_df[[
            "종목", "섹터", "보유 수량", "평균 매수가", "현재가", "평가액", "손익", "수익률"
        ]], hide_index=True, use_container_width=True)

        st.markdown("---")
        # 포트폴리오 요약 정보 표시 (calculate_portfolio_summary 함수 사용)
        cash, total_value, total_profit_loss, total_profit_rate, initial_cash = calculate_portfolio_summary()

        st.markdown(f"**💰 현금 잔고:** {cash:,.0f} 원")
        st.markdown(f"**📊 총 평가액 (주식 + 현금):** {total_value:,.0f} 원")
        st.markdown(f"**📈 총 손익:** {total_profit_loss:,.0f} 원")
        st.markdown(f"**🚀 총 수익률:** {total_profit_rate:.2f}%")
        # st.markdown(f"**🛒 총 매수 금액 (보유 주식):** {total_purchase_value_all:,.0f} 원") # 필요시 주석 해제
        # st.markdown(f"**🌱 시작 자본금:** {initial_cash:,.0f} 원") # 필요시 주석 해제

    else:
        st.info("보유 주식이 없습니다. '주식 매수' 탭에서 주식을 구매해보세요!")


# --- 주식 용어 사전 (수준별) ---
def display_stock_glossary():
    selected_level = st.session_state.get('selected_level', '초등')
    glossary = GLOSSARY.get(selected_level, GLOSSARY['초등']) # 해당 수준 없으면 초등 기본값

    with st.sidebar.expander(f"📚 주식 용어 사전 ({LEVELS[selected_level]['name']})", expanded=False):
        for term, definition in glossary.items():
            st.markdown(f"**{term}:** {definition}")
        st.markdown("---")


# --- 로그인 및 데이터 저장/로드 ---
def login_sidebar():
    # 이미 로그인된 경우
    if 'user_settings' in st.session_state and st.session_state['user_settings'] is not None:
        st.sidebar.success(f"{st.session_state['user_id']}님, 환영합니다!")
        # 로그아웃 버튼
        if st.sidebar.button("로그아웃"):
            # 세션 상태 초기화 (로그아웃 시 필요한 부분만)
            keys_to_reset = ["user_id", "user_settings", "portfolio", "stocks", "day_count", "daily_news", "previous_daily_news", "news_meanings", "initial_cash_set"]
            for key in keys_to_reset:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state['selected_level'] = "초등" # 레벨 기본값으로
            st.session_state['force_reset'] = True # 초기화 플래그 설정
            st.rerun() # 페이지 새로고침
        return True # 로그인 상태 반환

    # 로그인 폼
    st.sidebar.header("로그인")
    account = st.sidebar.text_input("아이디", key="login_id")
    pw = st.sidebar.text_input("비밀번호", type="password", key="login_pw")

    if st.sidebar.button("로그인", key="login_button"):
        if not supabase:
            st.error("데이터베이스 연결 오류로 로그인할 수 없습니다.")
            return False
        if not account or not pw:
            st.warning("아이디와 비밀번호를 입력해주세요.")
            return False
        try:
            response = supabase.table("users").select("*").eq("account", account).eq("pw", pw).execute()
            if response.data and len(response.data) > 0:
                user_data = response.data[0]
                st.session_state["user_id"] = user_data["account"] # 사용자 ID 저장
                st.session_state["selected_level"] = user_data.get("level", "초등") # 저장된 레벨 로드, 없으면 초등

                if "data" in user_data and user_data["data"]:
                    try:
                        user_settings = json.loads(user_data["data"])
                        # 저장된 게임 데이터 복원
                        for key in ["stocks", "previous_daily_news", "news_meanings", "day_count", "portfolio", "daily_news", "initial_cash_set"]:
                            if key in user_settings:
                                st.session_state[key] = user_settings[key]
                        st.session_state['user_settings'] = user_settings # 로드 성공 표시
                        st.success("로그인 성공! 게임 데이터를 불러왔습니다.")
                        # st.rerun() # 데이터 로드 후 화면 갱신 (아래에서 처리)
                    except json.JSONDecodeError:
                        st.error("저장된 데이터 형식 오류. 새 게임을 시작합니다.")
                        st.session_state['user_settings'] = {"new_user": True} # 오류 시 새 유저처럼
                        initialize_session_state(st.session_state["selected_level"]) # 초기화
                    except Exception as e:
                        st.error(f"데이터 로드 중 오류: {e}. 새 게임을 시작합니다.")
                        st.session_state['user_settings'] = {"new_user": True}
                        initialize_session_state(st.session_state["selected_level"])
                else:
                    st.info("저장된 게임 데이터가 없습니다. 새 게임을 시작합니다.")
                    st.session_state['user_settings'] = {"new_user": True} # 새 유저 표시
                    initialize_session_state(st.session_state["selected_level"]) # 초기화

                # 레벨 선택 드롭다운 업데이트 및 페이지 새로고침
                st.session_state['selected_level'] = user_data.get("level", "초등")
                st.rerun() # 로그인 성공 후 페이지 새로고침
            else:
                st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
        except Exception as e:
            st.error(f"로그인 중 오류 발생: {e}")
            return False

    # 회원가입 기능 제거됨

    return False # 로그인 안된 상태

def save_session_data():
    if supabase and 'user_id' in st.session_state and st.session_state['user_id']:
        keys_to_save = ["stocks", "previous_daily_news", "news_meanings", "day_count", "portfolio", "daily_news", "selected_level", "initial_cash_set"]
        data_to_save = {key: st.session_state[key] for key in keys_to_save if key in st.session_state}

        try:
            json_data = json.dumps(data_to_save, ensure_ascii=False, allow_nan=False, default=lambda o: '<not serializable>')
        except ValueError:
            def replace_nan_inf(obj):
                if isinstance(obj, dict):
                    return {k: replace_nan_inf(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [replace_nan_inf(elem) for elem in obj]
                elif isinstance(obj, float) and (obj != obj or obj == float('inf') or obj == float('-inf')):
                    return None
                return obj
            cleaned_data = replace_nan_inf(data_to_save)
            json_data = json.dumps(cleaned_data, ensure_ascii=False, allow_nan=False, default=lambda o: '<not serializable>')

        if json_data:
            try:
                supabase.table("users").update({"data": json_data}).eq("account", st.session_state["user_id"]).execute()
            except Exception as e:
                st.error(f"데이터 저장 중 오류 발생: {e}")


# --- 메인 앱 로직 ---
def main():
    # 로그인 상태 확인 및 처리
    is_logged_in = login_sidebar()

    # 로그인이 안 되어 있으면 메인 화면 표시 안 함
    if not is_logged_in:
        st.info("사이드바에서 로그인해주세요.")
        # 레벨 선택 (로그인 안했을 때만 보이도록) - 이 부분은 로그인 후 레벨 선택으로 통합됨
        # if 'user_settings' not in st.session_state or st.session_state['user_settings'] is None:
        #      selected_level = st.sidebar.selectbox(
        #          "학습 수준 선택 (로그인 전)",
        #          options=list(LEVELS.keys()),
        #          format_func=lambda x: LEVELS[x]['name'],
        #          key="level_selector_pre_login",
        #          index=list(LEVELS.keys()).index(st.session_state.get('selected_level', '초등')) # 기본값 반영
        #      )
        #      # 선택 시 세션 상태 업데이트 (로그인 전 임시)
        #      if st.session_state.get('selected_level') != selected_level:
        #          st.session_state['selected_level'] = selected_level
        #          # 레벨 변경 시 게임 상태 초기화 필요 알림 (선택적)
        #          st.sidebar.warning("레벨을 변경했습니다. 로그인 후 적용됩니다.")

        st.stop() # 메인 로직 중단

    # --- 로그인 후 ---

    # 세션 상태 초기화 (로그인 후 또는 새 게임 시작 시)
    # user_settings가 있고, new_user 플래그가 있거나, stocks/portfolio가 비정상일 때 초기화
    should_initialize = False
    if 'user_settings' not in st.session_state or st.session_state.get('user_settings', {}).get('new_user'):
        should_initialize = True
        if 'user_settings' in st.session_state and st.session_state.get('user_settings', {}).get('new_user'):
             st.session_state['user_settings'].pop('new_user') # new_user 플래그 제거
    elif "stocks" not in st.session_state or not st.session_state["stocks"] or "portfolio" not in st.session_state:
        st.warning("게임 데이터 일부가 유실되어 초기화합니다.")
        should_initialize = True

    if should_initialize:
        initialize_session_state(st.session_state['selected_level'])


    # 사이드바 상단에 레벨 선택 (로그인 후)
    current_level_index = list(LEVELS.keys()).index(st.session_state.get('selected_level', '초등'))
    selected_level = st.sidebar.selectbox(
        "학습 수준",
        options=list(LEVELS.keys()),
        format_func=lambda x: LEVELS[x]['name'],
        key="level_selector_post_login",
        index=current_level_index # 현재 레벨 반영
    )

    # 레벨 변경 감지 및 처리
    if st.session_state.get('selected_level') != selected_level:
        st.session_state['selected_level'] = selected_level
        st.sidebar.warning("학습 수준이 변경되었습니다. 용어 사전과 뉴스/해설의 난이도가 조정됩니다.")
        # 레벨 변경 시 게임 리셋 여부 확인 (선택적)
        if st.sidebar.button("⚠️ 레벨 변경 적용 (게임 초기화)", key="level_reset_confirm"):
             st.session_state['force_reset'] = True # 초기화 플래그
             initialize_session_state(selected_level) # 게임 상태 초기화
             save_session_data() # 변경된 레벨 및 초기화된 데이터 저장
             st.success("레벨이 변경되었고 게임이 초기화되었습니다.")
             st.rerun()
        else:
            st.sidebar.info("게임 초기화를 원하시면 위 버튼을 눌러주세요. 누르지 않으면 현재 게임 상태는 유지됩니다.")
            save_session_data() # 변경된 레벨만 저장
            st.rerun() # 화면 즉시 반영 (레벨 표시 등)


    # --- 메인 화면 구성 ---
    st.title(f"📈 {LEVELS[selected_level]['name']} 모의 주식 투자")

    # 사이드바 정보 표시
    with st.sidebar:
        st.markdown("---")
        st.markdown(f"### Day {st.session_state.get('day_count', 1)}") # 기본값 1
        st.markdown("---")
        # 포트폴리오 요약
        cash, total_value, total_profit_loss, total_profit_rate, _ = calculate_portfolio_summary()
        st.metric(label="💰 현금 잔고", value=f"{cash:,.0f} 원")
        st.metric(label="📊 총 평가 금액", value=f"{total_value:,.0f} 원", delta=f"{total_profit_loss:,.0f} 원")
        st.metric(label="🚀 총 수익률", value=f"{total_profit_rate:.2f}%")
        st.markdown("---")

        # 하루 지나기 버튼
        if st.button("☀️ 하루 지나기", use_container_width=True, key="day_pass_button"):
            if st.session_state.get("daily_news"):
                current_day = st.session_state.get('day_count', 1)
                with st.spinner(f"Day {current_day} 마감 및 Day {current_day + 1} 준비 중..."):
                    # 1. 현재 뉴스 저장 (이전 뉴스로)
                    st.session_state["previous_daily_news"] = st.session_state["daily_news"]
                    # 2. 이전 뉴스 해설 생성
                    meanings = explain_daily_news_meanings(st.session_state["previous_daily_news"])
                    if meanings:
                        st.session_state["news_meanings"] = meanings
                    else:
                        st.session_state["news_meanings"] = {} # 실패 시 초기화
                    # 3. 주가 업데이트 (뉴스 해설 기반)
                    update_stock_prices()
                    # 4. 다음 날 뉴스 생성
                    st.session_state["daily_news"] = generate_news()
                    # 5. 날짜 증가
                    st.session_state["day_count"] = current_day + 1
                    # 6. 상태 저장
                    save_session_data()
                st.success(f"Day {st.session_state['day_count']} 시작! 주가가 변동되었고 새로운 뉴스가 생성되었습니다.")
                st.toast("새로운 하루가 시작되었습니다!", icon="🌅")
                st.rerun() # 변경사항 반영 위해 새로고침
            else:
                st.warning("오늘의 뉴스를 먼저 생성해주세요.")
        st.markdown("---")

        # 용어 사전 표시
        display_stock_glossary()

        # 앱 가이드 표시
        with st.sidebar.expander("🚀 앱 사용 가이드", expanded=False):
            # (기존 가이드 내용 유지)
            st.markdown(
                """
        **1단계: 뉴스 생성하기**
        - 왼쪽 '오늘의 뉴스' 영역에서 '뉴스 생성' 버튼을 클릭하세요.
        - AI가 현재 설정된 학습 수준에 맞춰 주식 시장 뉴스를 5개 만들어줍니다.

        **2단계: 뉴스 읽고 예측하기**
        - 생성된 뉴스를 꼼꼼히 읽어보세요.
        - '어떤 종류의 회사가 이득을 볼까?' 또는 '어떤 회사가 어려울까?' 생각해보세요.
        - 뉴스를 통해 경제 흐름을 읽는 연습을 할 수 있습니다.

        **3단계: 주가 및 기업 정보 확인하기**
        - 메인 화면의 '📈 현재 주가' 탭에서 주식들의 현재 가격과 변동률을 확인하세요.
        - 관심 있는 종목을 선택하면 해당 기업에 대한 설명(수준별)과 주가 그래프를 볼 수 있습니다.

        **4단계: 주식 매수하기**
        - '💰 주식 매수' 탭에서 원하는 종목과 수량을 선택 후 '주식 매수' 버튼을 누르세요.
        - 정말 매수할지 확인 창이 뜹니다. '매수 확인'을 누르면 거래가 완료됩니다.
        - **팁:** 뉴스를 보고 유망하다고 생각되는 섹터의 주식을 골라보세요!

        **5단계: 내 포트폴리오 확인하기**
        - '📊 내 포트폴리오' 탭에서 내가 가진 주식과 현금 상황을 확인하세요.
        - 각 주식의 수익률과 총 자산 변화를 볼 수 있습니다.

        **6단계: 주식 매도하기**
        - '📉 주식 매도' 탭에서 팔고 싶은 주식과 수량을 선택 후 '주식 매도' 버튼을 누르세요.
        - 확인 창에서 '매도 확인'을 누르면 주식을 팔고 현금을 얻습니다.
        - **팁:** 주가가 충분히 올랐다고 생각될 때 팔아 이익을 실현해보세요!

        **7단계: 하루 지나기 & 뉴스 해설 보기**
        - 사이드바의 '☀️ 하루 지나기' 버튼을 클릭하면 시간이 흐릅니다.
        - 주가가 변동되고, 새로운 뉴스가 생성됩니다.
        - '📰 어제 뉴스 해설' 탭에서 AI가 분석한 이전 날 뉴스의 의미와 관련 섹터를 확인해보세요. (수준별 해설 제공)

        **꾸준히 학습하기! 🌱**
        - 매일 뉴스를 읽고, 투자를 결정하고, 결과를 확인하는 과정을 반복하며 경제와 투자에 대한 감각을 키워보세요!
        - 모르는 용어는 '📚 주식 용어 사전'을 참고하세요.
        """
            )

    # --- 메인 영역 레이아웃 ---
    col_news, col_main_ui = st.columns([1, 2]) # 뉴스 영역과 메인 UI 영역 분할

    with col_news:
        st.header(f"📰 Day {st.session_state.get('day_count', 1)} 뉴스")
        # 뉴스 생성 버튼
        if st.button("오늘의 뉴스 생성하기", use_container_width=True, key="news_gen_button", help="AI가 오늘의 경제 뉴스를 생성합니다."):
            with st.spinner(f"Day {st.session_state.get('day_count', 1)} 뉴스 생성 중... (수준: {LEVELS[selected_level]['name']})"):
                st.session_state["daily_news"] = generate_news()
                st.session_state["news_meanings"] = {} # 새 뉴스 생성 시 이전 해설 초기화
                save_session_data() # 뉴스 생성 후 저장
            st.rerun() # 뉴스 표시 위해 새로고침

        # 생성된 뉴스 표시
        if st.session_state.get("daily_news"):
            st.markdown("---")
            st.subheader("오늘의 주요 뉴스")
            for i, news in enumerate(st.session_state["daily_news"]):
                with st.expander(f"**뉴스 {i+1}**", expanded=(i==0)): # 첫 번째 뉴스만 펼치기
                    st.write(news)
            st.markdown("---")
            st.info("💡 뉴스를 읽고 어떤 섹터/기업에 영향이 있을지 예측해보세요! '하루 지나기' 후 '어제 뉴스 해설' 탭에서 AI 분석을 확인할 수 있습니다.")
        else:
            st.info("👆 '오늘의 뉴스 생성하기' 버튼을 눌러 뉴스를 받아보세요.")


    with col_main_ui:
        # 메인 탭 구성
        tab_titles = ['📈 현재 주가', '📊 내 포트폴리오', '💰 주식 매수', '📉 주식 매도', '📰 어제 뉴스 해설']
        tabs = st.tabs(tab_titles)

        with tabs[0]: # 현재 주가 탭
            st.subheader("📈 현재 주가 및 기업 정보")
            st.markdown("실시간 주가 변동과 기업 정보를 확인하세요. 종목 선택 시 상세 정보가 표시됩니다.")
            display_stock_prices()

        with tabs[1]: # 내 포트폴리오 탭
            st.subheader("📊 내 포트폴리오")
            st.markdown("보유 중인 주식과 자산 현황을 확인하세요.")
            display_portfolio_table()

        with tabs[2]: # 주식 매수 탭
            st.subheader("💰 주식 매수")
            st.markdown("투자하고 싶은 주식을 매수해보세요.")

            # 섹터 선택 -> 종목 선택 연동
            sector_names = ["섹터 선택..."] + list(st.session_state.get("stocks", {}).keys())
            selected_sector_buy = st.selectbox("1. 매수할 섹터 선택:", sector_names, key="buy_sector")

            if selected_sector_buy != "섹터 선택...":
                stock_names_in_sector = ["종목 선택..."] + list(st.session_state.get("stocks", {}).get(selected_sector_buy, {}).keys())
                selected_stock_buy = st.selectbox("2. 매수할 종목 선택:", stock_names_in_sector, key="buy_stock")

                if selected_stock_buy != "종목 선택...":
                    stock_info_buy = st.session_state.get("stocks", {}).get(selected_sector_buy, {}).get(selected_stock_buy)
                    if stock_info_buy: # 주식 정보 있는지 확인
                        stock_price_buy = stock_info_buy.get("current_price", 0)
                        # 수준별 설명 가져오기 (키 형식 변경 반영)
                        description_key = f"description_{selected_level}"
                        stock_description = stock_info_buy.get(description_key, stock_info_buy.get("description_중등","설명 없음"))

                        st.info(f"**{selected_stock_buy}** 현재 주가: **{stock_price_buy:,.0f}원**")
                        st.caption(f"기업 정보: {stock_description}")

                        # 매수 가능 수량 계산 및 표시
                        available_cash = st.session_state.get("portfolio", {}).get("cash", 0)
                        max_buy_quantity = available_cash // stock_price_buy if stock_price_buy > 0 else 0
                        st.caption(f"현금 잔고: {available_cash:,.0f}원 (최대 {max_buy_quantity}주 매수 가능)")

                        quantity_buy = st.number_input(
                            f"3. 매수 수량 입력 (최대 {max_buy_quantity}주):",
                            min_value=1,
                            max_value=max(1, max_buy_quantity), # 0주 방지, 최대값 1 이상
                            value=1,
                            step=1,
                            key="buy_quantity",
                            disabled=(max_buy_quantity == 0) # 잔액 없으면 비활성화
                        )

                        total_buy_price = stock_price_buy * quantity_buy
                        st.markdown(f"**예상 매수 금액:** {total_buy_price:,.0f} 원")

                        # 매수 확인 절차
                        if not st.session_state.get('buy_confirm', False):
                            if st.button("주식 매수", use_container_width=True, key='buy_button_confirm', disabled=(max_buy_quantity == 0 or quantity_buy <= 0)):
                                if quantity_buy > max_buy_quantity:
                                    st.error(f"매수 가능 수량 초과! (최대 {max_buy_quantity}주)")
                                elif quantity_buy <= 0:
                                    st.error("매수 수량은 1주 이상이어야 합니다.")
                                else:
                                    st.session_state['buy_confirm'] = True
                                    st.rerun() # 확인 UI 표시 위해 새로고침
                        else:
                            st.warning(f"**{selected_stock_buy} {quantity_buy}주**를 **{total_buy_price:,.0f}원**에 매수하시겠습니까?")
                            col_confirm, col_cancel = st.columns([1, 1])
                            with col_confirm:
                                if st.button("✅ 네, 매수합니다", use_container_width=True, key='buy_confirm_button'):
                                    buy_stock(selected_stock_buy, quantity_buy, selected_sector_buy)
                                    st.rerun() # 포트폴리오 업데이트 반영
                            with col_cancel:
                                if st.button("❌ 아니요, 취소합니다", use_container_width=True, key='buy_cancel_button'):
                                    st.session_state['buy_confirm'] = False
                                    st.info("매수를 취소했습니다.")
                                    st.rerun() # 확인 UI 숨기기
                    else:
                        st.warning("선택한 종목 정보를 불러올 수 없습니다.")
            else:
                st.info("먼저 매수할 섹터를 선택해주세요.")


        with tabs[3]: # 주식 매도 탭
            st.subheader("📉 주식 매도")
            st.markdown("보유 중인 주식을 판매하여 현금화하세요.")

            portfolio_stocks = st.session_state.get("portfolio", {}).get("stocks", {})
            if portfolio_stocks:
                owned_stock_names = ["종목 선택..."] + list(portfolio_stocks.keys())
                selected_stock_sell = st.selectbox("1. 매도할 종목 선택:", owned_stock_names, key="sell_stock")

                if selected_stock_sell != "종목 선택...":
                    stock_info_sell = portfolio_stocks.get(selected_stock_sell)
                    if stock_info_sell: # 보유 정보 있는지 확인
                        owned_quantity = stock_info_sell.get("quantity", 0)
                        purchase_price_avg = stock_info_sell.get("purchase_price", 0)

                        # 현재가 찾기
                        current_price_sell = 0
                        for sector, stocks_in_sector in st.session_state.get("stocks", {}).items():
                            if selected_stock_sell in stocks_in_sector:
                                current_price_sell = stocks_in_sector[selected_stock_sell].get("current_price", 0)
                                break

                        st.info(f"**{selected_stock_sell}** 보유 수량: **{owned_quantity}주**")
                        st.caption(f"평균 매수가: {purchase_price_avg:,.0f}원 / 현재가: {current_price_sell:,.0f}원")

                        quantity_sell = st.number_input(
                            f"2. 매도 수량 입력 (최대 {owned_quantity}주):",
                            min_value=1,
                            max_value=owned_quantity,
                            value=1,
                            step=1,
                            key="sell_quantity",
                            disabled=(owned_quantity == 0) # 보유량 없으면 비활성화
                        )

                        total_sell_price = current_price_sell * quantity_sell
                        st.markdown(f"**예상 매도 금액:** {total_sell_price:,.0f} 원")

                        # 매도 확인 절차
                        if not st.session_state.get('sell_confirm', False):
                            if st.button("주식 매도", use_container_width=True, key='sell_button_confirm', disabled=(owned_quantity == 0 or quantity_sell <= 0)):
                                if quantity_sell > owned_quantity:
                                    st.error(f"매도 가능 수량 초과! (최대 {owned_quantity}주)")
                                elif quantity_sell <= 0:
                                    st.error("매도 수량은 1주 이상이어야 합니다.")
                                else:
                                    st.session_state['sell_confirm'] = True
                                    st.rerun()
                        else:
                            st.warning(f"**{selected_stock_sell} {quantity_sell}주**를 **{total_sell_price:,.0f}원**에 매도하시겠습니까?")
                            col_confirm, col_cancel = st.columns([1, 1])
                            with col_confirm:
                                if st.button("✅ 네, 매도합니다", use_container_width=True, key='sell_confirm_button'):
                                    sell_stock(selected_stock_sell, quantity_sell)
                                    st.rerun()
                            with col_cancel:
                                if st.button("❌ 아니요, 취소합니다", use_container_width=True, key='sell_cancel_button'):
                                    st.session_state['sell_confirm'] = False
                                    st.info("매도를 취소했습니다.")
                                    st.rerun()
                    else:
                        st.warning("선택한 보유 주식 정보를 찾을 수 없습니다.")
            else:
                st.info("매도할 주식이 없습니다. 먼저 주식을 매수하세요.")

        with tabs[4]: # 어제 뉴스 해설 탭
            st.subheader(f"📰 Day {st.session_state.get('day_count', 1) - 1} 뉴스 해설")
            st.markdown(f"AI가 분석한 어제 뉴스의 의미와 관련 섹터입니다. ({LEVELS[selected_level]['name']} 수준)")

            previous_daily_news = st.session_state.get("previous_daily_news")
            news_meanings = st.session_state.get("news_meanings")

            if previous_daily_news and news_meanings:
                if len(previous_daily_news) == len(news_meanings):
                    for i in range(len(previous_daily_news)):
                        news_index_str = str(i + 1)
                        meaning_data = news_meanings.get(news_index_str)
                        if meaning_data: # 해설 데이터 있는지 확인
                            with st.expander(f"**뉴스 {news_index_str}**", expanded=False):
                                st.markdown("**어제 뉴스 원문:**")
                                st.write(previous_daily_news[i])
                                st.markdown("---")
                                st.markdown("**AI 해설:**")
                                explanation = meaning_data.get("explanation", "해설 없음")
                                sectors = meaning_data.get("sectors", [])
                                st.info(explanation)
                                if sectors:
                                    st.markdown("**관련 섹터:**")
                                    st.success(f"{', '.join(sectors)}")
                                else:
                                    st.markdown("**관련 섹터:** 없음")
                        else:
                            st.warning(f"뉴스 {news_index_str}에 대한 해설 데이터를 찾을 수 없습니다.")
                else:
                    st.warning("뉴스 개수와 해설 개수가 일치하지 않습니다. 데이터 오류 가능성이 있습니다.")

            elif st.session_state.get('day_count', 1) == 1:
                 st.info("첫 날에는 이전 뉴스가 없습니다. '하루 지나기'를 눌러 다음 날로 이동하세요.")
            else:
                st.info("아직 어제 뉴스에 대한 해설이 생성되지 않았습니다. '하루 지나기'를 진행했는지 확인해주세요.")


if __name__ == "__main__":
    # 앱 시작 시 초기 레벨 설정 (세션 상태에 없으면 기본값)
    if 'selected_level' not in st.session_state:
        st.session_state['selected_level'] = "초등"
    main()