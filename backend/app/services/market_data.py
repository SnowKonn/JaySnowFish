"""
금융시장 데이터 서비스
공개 데이터 소스에서 시세와 거시경제 데이터를 가져와 시뮬레이션에 사용할
"시장 시드 텍스트"로 변환한다.

지원하는 데이터 소스:
- Stooq: 무료, 키 불필요. 주식/지수/외환/원자재의 일봉 과거 시세 제공
- Yahoo Finance: 무료, 키 불필요. 공개 chart 엔드포인트로 시세 조회
- Alpha Vantage: 주식/외환/암호화폐 시세 (ALPHA_VANTAGE_API_KEY 필요)
- FRED: 미국 연준 거시경제 데이터 (FRED_API_KEY 필요)
- OECD: OECD 거시경제 데이터, 무료·키 불필요 (SDMX-JSON 인터페이스)
- 한국은행 ECOS: 한국 거시경제 통계 (ECOS_API_KEY 필요)

시드 텍스트는 그래프 구축 및 본체(ontology) 생성 과정에 문서로 입력되어,
시뮬레이션이 실제 시장 데이터를 기반으로 진행되도록 한다.
"""

import csv
import io
import json
import urllib.parse
import urllib.request
from typing import Dict, Any, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.market_data')

_HTTP_TIMEOUT = 20


def _http_get(url: str) -> str:
    """HTTP GET 요청을 보내고 텍스트 응답을 반환한다."""
    req = urllib.request.Request(url, headers={'User-Agent': 'MiroFish-MarketData/1.0'})
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        return resp.read().decode('utf-8', errors='replace')


def _summarize_ohlcv(symbol: str, rows: List[Dict[str, str]], lookback: int) -> str:
    """OHLCV 시세 레코드를 자연어 요약문으로 변환한다."""
    parsed = []
    for r in rows:
        try:
            close = float(str(r.get('Close', r.get('close', ''))).replace(',', ''))
        except (ValueError, TypeError):
            continue
        parsed.append({
            'date': r.get('Date', r.get('date', '')),
            'open': r.get('Open', r.get('open', '')),
            'high': r.get('High', r.get('high', '')),
            'low': r.get('Low', r.get('low', '')),
            'close': close,
            'volume': r.get('Volume', r.get('volume', '')),
        })
    if not parsed:
        return f"종목 {symbol}: 유효한 시세 데이터를 가져오지 못했습니다."

    parsed = parsed[-lookback:]
    first_c = parsed[0]['close']
    last_c = parsed[-1]['close']
    change_pct = ((last_c - first_c) / first_c * 100) if first_c else 0.0
    highs = [p['close'] for p in parsed]
    period_high = max(highs)
    period_low = min(highs)

    trend = "상승" if change_pct > 1 else "하락" if change_pct < -1 else "횡보"
    lines = [
        f"## 종목 시세: {symbol}",
        f"기간: {parsed[0]['date']} ~ {parsed[-1]['date']} (총 {len(parsed)} 거래일)",
        f"종가가 {first_c:g}에서 {last_c:g}로 변동, 기간 등락률 {change_pct:+.2f}%로 전반적으로 {trend} 추세.",
        f"기간 종가 최고 {period_high:g}, 최저 {period_low:g}.",
        "최근 일별 시세:",
    ]
    for p in parsed[-15:]:
        lines.append(f"  {p['date']}: 시가 {p['open']}, 고가 {p['high']}, 저가 {p['low']}, "
                      f"종가 {p['close']:g}, 거래량 {p['volume']}")
    return "\n".join(lines)


def _summarize_series(title: str, points: List[tuple], lookback: int) -> str:
    """
    일반 시계열(거시 지표)을 자연어 요약문으로 변환한다.

    Args:
        title: 지표 제목
        points: 시간 오름차순으로 정렬된 [(date, value_str), ...]
        lookback: 최근 N개의 관측치를 사용
    """
    clean = []
    for date, raw in points:
        if raw in (None, '', '.'):
            continue
        try:
            clean.append((date, float(str(raw).replace(',', ''))))
        except (ValueError, TypeError):
            continue
    if not clean:
        return f"## {title}\n유효한 데이터를 가져오지 못했습니다."

    clean = clean[-lookback:]
    first_v, last_v = clean[0][1], clean[-1][1]
    change_pct = ((last_v - first_v) / first_v * 100) if first_v else 0.0
    lines = [
        f"## {title}",
        f"기간: {clean[0][0]} ~ {clean[-1][0]} (총 {len(clean)}개 관측치)",
        f"수치가 {first_v:g}에서 {last_v:g}로 변동, 기간 변화율 {change_pct:+.2f}%.",
        "최근 관측치:",
    ]
    for date, val in clean[-15:]:
        lines.append(f"  {date}: {val:g}")
    return "\n".join(lines)


def fetch_stooq(symbol: str, lookback: int = None) -> str:
    """
    Stooq에서 일봉 시세를 가져와 요약 텍스트를 생성한다.

    Args:
        symbol: Stooq 코드. 예) 미국 주식 'aapl.us', S&P500 지수 '^spx', 달러 지수 'usdidx'
        lookback: 최근 N 거래일. 미지정 시 설정값 사용

    Returns:
        시세 요약 텍스트
    """
    lookback = lookback or Config.MARKET_DATA_DEFAULT_LOOKBACK
    url = f"{Config.STOOQ_BASE_URL}?{urllib.parse.urlencode({'s': symbol, 'i': 'd'})}"
    try:
        text = _http_get(url)
    except Exception as e:
        logger.warning(f"Stooq 조회 실패 {symbol}: {e}")
        return f"종목 {symbol}: 시세 조회에 실패했습니다 ({e})."

    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return f"종목 {symbol}: Stooq가 데이터를 반환하지 않았습니다. 코드 형식을 확인하세요 (예: 'aapl.us', '^spx')."
    return _summarize_ohlcv(symbol, rows, lookback)


def fetch_yahoo(symbol: str, lookback: int = None) -> str:
    """
    Yahoo Finance 공개 chart 엔드포인트로 일봉 시세를 가져온다 (무료, 키 불필요).

    Args:
        symbol: Yahoo 코드. 예) 미국 주식 'AAPL', S&P500 지수 '^GSPC', 한국 KOSPI '^KS11'.
                한국 주식은 거래소 접미사가 필요함. 예) 삼성전자 '005930.KS'
        lookback: 최근 N 거래일
    """
    lookback = lookback or Config.MARKET_DATA_DEFAULT_LOOKBACK
    params = urllib.parse.urlencode({'range': '1y', 'interval': '1d'})
    url = f"{Config.YAHOO_CHART_BASE_URL}{urllib.parse.quote(symbol)}?{params}"
    try:
        data = json.loads(_http_get(url))
    except Exception as e:
        logger.warning(f"Yahoo Finance 조회 실패 {symbol}: {e}")
        return f"종목 {symbol}: Yahoo Finance 조회에 실패했습니다 ({e})."

    chart = (data.get('chart') or {})
    results = chart.get('result')
    if not results:
        err = (chart.get('error') or {}).get('description', '데이터 없음')
        return f"종목 {symbol}: Yahoo Finance가 시세를 반환하지 않았습니다 ({err})."

    res = results[0]
    timestamps = res.get('timestamp') or []
    quote = ((res.get('indicators') or {}).get('quote') or [{}])[0]
    import datetime
    rows = []
    for i, ts in enumerate(timestamps):
        def at(key):
            arr = quote.get(key) or []
            return arr[i] if i < len(arr) and arr[i] is not None else ''
        if at('close') == '':
            continue
        rows.append({
            'Date': datetime.datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d'),
            'Open': at('open'), 'High': at('high'), 'Low': at('low'),
            'Close': at('close'), 'Volume': at('volume'),
        })
    if not rows:
        return f"종목 {symbol}: Yahoo Finance가 유효한 시세를 반환하지 않았습니다."
    return _summarize_ohlcv(symbol, rows, lookback)


def fetch_alpha_vantage(symbol: str, lookback: int = None) -> str:
    """Alpha Vantage에서 일봉 시세를 가져온다 (API 키 필요)."""
    lookback = lookback or Config.MARKET_DATA_DEFAULT_LOOKBACK
    if not Config.ALPHA_VANTAGE_API_KEY:
        return f"종목 {symbol}: ALPHA_VANTAGE_API_KEY가 설정되지 않아 Alpha Vantage 소스를 건너뜁니다."

    params = urllib.parse.urlencode({
        'function': 'TIME_SERIES_DAILY',
        'symbol': symbol,
        'outputsize': 'compact',
        'apikey': Config.ALPHA_VANTAGE_API_KEY,
    })
    try:
        data = json.loads(_http_get(f"https://www.alphavantage.co/query?{params}"))
    except Exception as e:
        logger.warning(f"Alpha Vantage 조회 실패 {symbol}: {e}")
        return f"종목 {symbol}: Alpha Vantage 조회에 실패했습니다 ({e})."

    series = data.get('Time Series (Daily)')
    if not series:
        note = data.get('Note') or data.get('Information') or data.get('Error Message') or '데이터 없음'
        return f"종목 {symbol}: Alpha Vantage가 시세를 반환하지 않았습니다 ({note})."

    rows = []
    for date in sorted(series.keys()):
        d = series[date]
        rows.append({
            'Date': date,
            'Open': d.get('1. open', ''),
            'High': d.get('2. high', ''),
            'Low': d.get('3. low', ''),
            'Close': d.get('4. close', ''),
            'Volume': d.get('5. volume', ''),
        })
    return _summarize_ohlcv(symbol, rows, lookback)


def fetch_fred(series_id: str, lookback: int = None) -> str:
    """
    FRED에서 거시경제 시계열을 가져온다 (API 키 필요).

    Args:
        series_id: FRED 시리즈 코드. 예) 'CPIAUCSL'(CPI), 'FEDFUNDS'(연방기금금리), 'UNRATE'(실업률)
    """
    lookback = lookback or Config.MARKET_DATA_DEFAULT_LOOKBACK
    if not Config.FRED_API_KEY:
        return f"거시 지표 {series_id}: FRED_API_KEY가 설정되지 않아 FRED 소스를 건너뜁니다."

    params = urllib.parse.urlencode({
        'series_id': series_id,
        'api_key': Config.FRED_API_KEY,
        'file_type': 'json',
        'sort_order': 'desc',
        'limit': lookback,
    })
    try:
        data = json.loads(_http_get(f"https://api.stlouisfed.org/fred/series/observations?{params}"))
    except Exception as e:
        logger.warning(f"FRED 조회 실패 {series_id}: {e}")
        return f"거시 지표 {series_id}: FRED 조회에 실패했습니다 ({e})."

    obs = list(reversed(data.get('observations', [])))  # 시간 오름차순으로 변환
    if not obs:
        return f"거시 지표 {series_id}: FRED가 데이터를 반환하지 않았습니다."
    points = [(o.get('date', ''), o.get('value')) for o in obs]
    return _summarize_series(f"거시 지표(FRED): {series_id}", points, lookback)


def fetch_oecd(dataflow_query: str, lookback: int = None) -> str:
    """
    OECD SDMX-JSON 인터페이스에서 거시경제 시계열을 가져온다 (무료, 키 불필요).

    Args:
        dataflow_query: SDMX 데이터 조회 경로. 예)
            'OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA,1.0/Q..USA...G1.'
            OECD Data Explorer의 "개발자 API" 메뉴에서 복사할 수 있음
        lookback: 최근 N개의 관측치를 사용
    """
    lookback = lookback or Config.MARKET_DATA_DEFAULT_LOOKBACK
    params = urllib.parse.urlencode({'format': 'jsondata', 'dimensionAtObservation': 'AllDimensions'})
    url = f"{Config.OECD_SDMX_BASE_URL}{dataflow_query}?{params}"
    try:
        data = json.loads(_http_get(url))
    except Exception as e:
        logger.warning(f"OECD 조회 실패 {dataflow_query}: {e}")
        return f"OECD 지표 {dataflow_query}: 조회에 실패했습니다 ({e})."

    try:
        dataset = (data.get('data', data).get('dataSets') or [{}])[0]
        structure = data.get('data', data).get('structure', {})
        dims = (structure.get('dimensions', {}).get('observation')
                or structure.get('dimensions', {}).get('series') or [])
        time_dim = next((d for d in dims if d.get('id') in ('TIME_PERIOD', 'TIME')), None)
        time_values = [v.get('name') or v.get('id') for v in time_dim.get('values', [])] if time_dim else []
        time_index = dims.index(time_dim) if time_dim in dims else -1

        observations = dataset.get('observations', {})
        points = []
        for key, val in observations.items():
            parts = key.split(':')
            label = (time_values[int(parts[time_index])]
                     if 0 <= time_index < len(parts) and time_values else key)
            value = val[0] if isinstance(val, list) and val else val
            points.append((str(label), value))
        points.sort(key=lambda p: p[0])
    except Exception as e:
        logger.warning(f"OECD 파싱 실패 {dataflow_query}: {e}")
        return f"OECD 지표 {dataflow_query}: 데이터 파싱에 실패했습니다 ({e})."

    if not points:
        return f"OECD 지표 {dataflow_query}: 관측 데이터를 반환하지 않았습니다."
    return _summarize_series(f"거시 지표(OECD): {dataflow_query}", points, lookback)


def fetch_ecos(stat_code: str, item_code: str = '', cycle: str = 'M',
               start: str = '', end: str = '', count: int = 100) -> str:
    """
    한국은행 ECOS 인터페이스에서 한국 거시경제 통계를 가져온다 (ECOS_API_KEY 필요).

    Args:
        stat_code: 통계표 코드. 예) '722Y001'(기준금리), '901Y009'(소비자물가지수)
        item_code: 통계 항목 코드 (일부 통계표는 필수)
        cycle: 주기. 'D' 일 / 'M' 월 / 'Q' 분기 / 'A' 연
        start, end: 시작·종료 시점. 주기 형식에 맞춤 (월 'YYYYMM', 연 'YYYY', 일 'YYYYMMDD')
        count: 최대 반환 건수
    """
    if not Config.ECOS_API_KEY:
        return f"한국 거시 지표 {stat_code}: ECOS_API_KEY가 설정되지 않아 ECOS 소스를 건너뜁니다."

    if not start or not end:
        defaults = {'D': ('20000101', '20991231'), 'M': ('200001', '209912'),
                    'Q': ('2000Q1', '2099Q4'), 'A': ('2000', '2099')}
        d_start, d_end = defaults.get(cycle, ('200001', '209912'))
        start, end = start or d_start, end or d_end

    segments = ['StatisticSearch', Config.ECOS_API_KEY, 'json', 'kr',
                '1', str(count), stat_code, cycle, start, end]
    if item_code:
        segments.append(item_code)
    url = 'https://ecos.bok.or.kr/api/' + '/'.join(urllib.parse.quote(s, safe='') for s in segments)
    try:
        data = json.loads(_http_get(url))
    except Exception as e:
        logger.warning(f"ECOS 조회 실패 {stat_code}: {e}")
        return f"한국 거시 지표 {stat_code}: ECOS 조회에 실패했습니다 ({e})."

    if 'RESULT' in data:
        msg = data['RESULT'].get('MESSAGE', '조회 실패')
        return f"한국 거시 지표 {stat_code}: ECOS가 오류를 반환했습니다 ({msg})."

    rows = (data.get('StatisticSearch') or {}).get('row') or []
    if not rows:
        return f"한국 거시 지표 {stat_code}: ECOS가 데이터를 반환하지 않았습니다."

    title = rows[0].get('STAT_NAME', stat_code)
    item_name = rows[0].get('ITEM_NAME1', '')
    points = [(r.get('TIME', ''), r.get('DATA_VALUE')) for r in rows]
    points.sort(key=lambda p: p[0])
    label = f"한국 거시 지표(ECOS): {title}" + (f" - {item_name}" if item_name else "")
    lookback = count
    return _summarize_series(label, points, lookback)


_STOCK_FETCHERS = {
    'stooq': fetch_stooq,
    'yahoo': fetch_yahoo,
    'alpha_vantage': fetch_alpha_vantage,
}


def build_market_seed(
    stocks: Optional[List[str]] = None,
    stock_source: str = 'stooq',
    fred_series: Optional[List[str]] = None,
    oecd_queries: Optional[List[str]] = None,
    ecos_series: Optional[List[Any]] = None,
    lookback: int = None,
) -> str:
    """
    종합적인 "시장 시드 텍스트"를 구성한다. 시뮬레이션의 실제 데이터 입력으로 사용된다.

    Args:
        stocks: 종목 코드 목록. 형식은 stock_source에 따라 다름
        stock_source: 시세 데이터 소스. 'stooq' / 'yahoo' / 'alpha_vantage'
        fred_series: FRED 거시 시리즈 코드 목록 (예: ['FEDFUNDS', 'CPIAUCSL'])
        oecd_queries: OECD SDMX 데이터 조회 경로 목록
        ecos_series: 한국은행 ECOS 조회 목록. 원소는 통계표 코드 문자열이거나,
                     dict(stat_code / item_code / cycle / start / end / count 포함)
        lookback: 최근 N 거래일/관측치를 사용

    Returns:
        결합된 시장 시드 텍스트. 그래프 구축 과정에 문서로 바로 입력 가능
    """
    sections = ["# 금융시장 데이터 시드",
                "본 문서는 실제 시장 데이터로 자동 생성되었으며, 금융시장 예측 시뮬레이션을 구동하는 데 사용된다.", ""]

    fetch_stock = _STOCK_FETCHERS.get(stock_source, fetch_stooq)
    for symbol in (stocks or []):
        sections.append(fetch_stock(symbol, lookback))
        sections.append("")

    for series_id in (fred_series or []):
        sections.append(fetch_fred(series_id, lookback))
        sections.append("")

    for query in (oecd_queries or []):
        sections.append(fetch_oecd(query, lookback))
        sections.append("")

    for item in (ecos_series or []):
        if isinstance(item, dict):
            sections.append(fetch_ecos(**item))
        else:
            sections.append(fetch_ecos(str(item)))
        sections.append("")

    if not any([stocks, fred_series, oecd_queries, ecos_series]):
        sections.append("(지정된 종목이나 거시 지표가 없습니다)")

    return "\n".join(sections)
