"""
설정 관리
프로젝트 루트 디렉토리의 .env 파일에서 통합 설정 로드
"""

import os
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리의 .env 파일 로드
# 경로: MiroFish/.env (backend/app/config.py 기준 상대 경로)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # 루트 디렉토리에 .env가 없으면 환경 변수 로드 시도 (프로덕션 환경용)
    load_dotenv(override=True)


class Config:
    """Flask 설정 클래스"""

    # Flask 설정
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    # JSON 설정 - ASCII 이스케이프 비활성화, 한글/중문 직접 표시 (\uXXXX 형식 대신)
    JSON_AS_ASCII = False

    # LLM 설정 (OpenAI 형식 통일 사용)
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')

    # Zep 설정
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')

    # 파일 업로드 설정
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown', 'csv'}

    # ===== 금융시장 데이터 소스 설정 =====
    # Stooq: 무료·키 불필요. 주식/지수/외환/원자재의 과거 및 일봉 데이터 제공
    STOOQ_BASE_URL = os.environ.get('STOOQ_BASE_URL', 'https://stooq.com/q/d/l/')
    # Yahoo Finance: 무료·키 불필요. 공개 chart 엔드포인트로 시세 조회
    YAHOO_CHART_BASE_URL = os.environ.get(
        'YAHOO_CHART_BASE_URL', 'https://query1.finance.yahoo.com/v8/finance/chart/')
    # Alpha Vantage: 주식/외환/암호화폐 시세 (무료 API 키 필요)
    ALPHA_VANTAGE_API_KEY = os.environ.get('ALPHA_VANTAGE_API_KEY')
    # FRED: 미국 연준 거시경제 데이터 (금리, CPI, 실업률 등. 무료 API 키 필요)
    FRED_API_KEY = os.environ.get('FRED_API_KEY')
    # OECD: OECD 거시경제 데이터. 무료·키 불필요 (SDMX-JSON 인터페이스)
    OECD_SDMX_BASE_URL = os.environ.get(
        'OECD_SDMX_BASE_URL', 'https://sdmx.oecd.org/public/rest/data/')
    # 한국은행 ECOS: 한국 거시경제 통계 (무료 API 키 필요)
    ECOS_API_KEY = os.environ.get('ECOS_API_KEY')
    # 시드 텍스트 생성 시 기본으로 가져올 최근 거래일 수
    MARKET_DATA_DEFAULT_LOOKBACK = int(os.environ.get('MARKET_DATA_DEFAULT_LOOKBACK', '60'))

    # 텍스트 처리 설정
    DEFAULT_CHUNK_SIZE = 500  # 기본 청크 크기
    DEFAULT_CHUNK_OVERLAP = 50  # 기본 중첩 크기

    # OASIS 시뮬레이션 설정
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')

    # OASIS 플랫폼 사용 가능 액션 설정
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]

    # Report Agent 설정
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    @classmethod
    def validate(cls):
        """필수 설정 검증"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 미설정")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY 미설정")
        return errors

