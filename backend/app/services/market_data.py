"""
金融市场数据服务
从公开数据源抓取行情与宏观经济数据，转换为可用于模拟的"市场种子文本"。

支持的数据源：
- Stooq：免费、无需密钥，提供股票/指数/外汇/商品的日线历史行情
- Yahoo Finance：免费、无需密钥，通过公开 chart 接口抓取行情
- Alpha Vantage：股票/外汇/加密货币行情（需 ALPHA_VANTAGE_API_KEY）
- FRED：美联储宏观经济数据（需 FRED_API_KEY）
- OECD：经合组织宏观经济数据，免费、无需密钥（SDMX-JSON 接口）
- 韩国银行 ECOS：韩国宏观经济统计（需 ECOS_API_KEY）

种子文本会作为文档输入图谱构建与本体生成流程，使模拟基于真实市场数据展开。
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
    """发起 HTTP GET 请求并返回文本内容"""
    req = urllib.request.Request(url, headers={'User-Agent': 'MiroFish-MarketData/1.0'})
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        return resp.read().decode('utf-8', errors='replace')


def _summarize_ohlcv(symbol: str, rows: List[Dict[str, str]], lookback: int) -> str:
    """将 OHLCV 行情记录转换为自然语言摘要"""
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
        return f"标的 {symbol}：未获取到有效行情数据。"

    parsed = parsed[-lookback:]
    first_c = parsed[0]['close']
    last_c = parsed[-1]['close']
    change_pct = ((last_c - first_c) / first_c * 100) if first_c else 0.0
    highs = [p['close'] for p in parsed]
    period_high = max(highs)
    period_low = min(highs)

    trend = "上涨" if change_pct > 1 else "下跌" if change_pct < -1 else "震荡"
    lines = [
        f"## 标的行情：{symbol}",
        f"区间：{parsed[0]['date']} 至 {parsed[-1]['date']}（共 {len(parsed)} 个交易日）",
        f"收盘价自 {first_c:g} 变化至 {last_c:g}，区间涨跌幅 {change_pct:+.2f}%，整体呈{trend}态势。",
        f"区间收盘最高 {period_high:g}，最低 {period_low:g}。",
        "近期逐日收盘：",
    ]
    for p in parsed[-15:]:
        lines.append(f"  {p['date']}：开 {p['open']}，高 {p['high']}，低 {p['low']}，"
                      f"收 {p['close']:g}，量 {p['volume']}")
    return "\n".join(lines)


def _summarize_series(title: str, points: List[tuple], lookback: int) -> str:
    """
    将通用时间序列（宏观指标）转换为自然语言摘要。

    Args:
        title: 指标标题
        points: 已按时间正序排列的 [(date, value_str), ...]
        lookback: 取最近 N 个观测点
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
        return f"## {title}\n未获取到有效数据。"

    clean = clean[-lookback:]
    first_v, last_v = clean[0][1], clean[-1][1]
    change_pct = ((last_v - first_v) / first_v * 100) if first_v else 0.0
    lines = [
        f"## {title}",
        f"区间：{clean[0][0]} 至 {clean[-1][0]}（共 {len(clean)} 个观测点）",
        f"数值自 {first_v:g} 变化至 {last_v:g}，区间变化 {change_pct:+.2f}%。",
        "近期观测：",
    ]
    for date, val in clean[-15:]:
        lines.append(f"  {date}：{val:g}")
    return "\n".join(lines)


def fetch_stooq(symbol: str, lookback: int = None) -> str:
    """
    从 Stooq 抓取日线行情并生成摘要文本。

    Args:
        symbol: Stooq 代码，如美股 'aapl.us'、标普500指数 '^spx'、美元指数 'usdidx'
        lookback: 取最近 N 个交易日，默认取配置值

    Returns:
        行情摘要文本
    """
    lookback = lookback or Config.MARKET_DATA_DEFAULT_LOOKBACK
    url = f"{Config.STOOQ_BASE_URL}?{urllib.parse.urlencode({'s': symbol, 'i': 'd'})}"
    try:
        text = _http_get(url)
    except Exception as e:
        logger.warning(f"Stooq 抓取失败 {symbol}: {e}")
        return f"标的 {symbol}：行情抓取失败（{e}）。"

    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return f"标的 {symbol}：Stooq 未返回数据，请检查代码格式（如 'aapl.us'、'^spx'）。"
    return _summarize_ohlcv(symbol, rows, lookback)


def fetch_yahoo(symbol: str, lookback: int = None) -> str:
    """
    通过 Yahoo Finance 公开 chart 接口抓取日线行情（免费、无需密钥）。

    Args:
        symbol: Yahoo 代码，如美股 'AAPL'、标普500指数 '^GSPC'、韩国KOSPI '^KS11'、
                韩股需带交易所后缀如三星电子 '005930.KS'
        lookback: 取最近 N 个交易日
    """
    lookback = lookback or Config.MARKET_DATA_DEFAULT_LOOKBACK
    params = urllib.parse.urlencode({'range': '1y', 'interval': '1d'})
    url = f"{Config.YAHOO_CHART_BASE_URL}{urllib.parse.quote(symbol)}?{params}"
    try:
        data = json.loads(_http_get(url))
    except Exception as e:
        logger.warning(f"Yahoo Finance 抓取失败 {symbol}: {e}")
        return f"标的 {symbol}：Yahoo Finance 抓取失败（{e}）。"

    chart = (data.get('chart') or {})
    results = chart.get('result')
    if not results:
        err = (chart.get('error') or {}).get('description', '无数据')
        return f"标的 {symbol}：Yahoo Finance 未返回行情（{err}）。"

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
        return f"标的 {symbol}：Yahoo Finance 未返回有效行情。"
    return _summarize_ohlcv(symbol, rows, lookback)


def fetch_alpha_vantage(symbol: str, lookback: int = None) -> str:
    """从 Alpha Vantage 抓取日线行情（需 API Key）"""
    lookback = lookback or Config.MARKET_DATA_DEFAULT_LOOKBACK
    if not Config.ALPHA_VANTAGE_API_KEY:
        return f"标的 {symbol}：未配置 ALPHA_VANTAGE_API_KEY，已跳过 Alpha Vantage 数据源。"

    params = urllib.parse.urlencode({
        'function': 'TIME_SERIES_DAILY',
        'symbol': symbol,
        'outputsize': 'compact',
        'apikey': Config.ALPHA_VANTAGE_API_KEY,
    })
    try:
        data = json.loads(_http_get(f"https://www.alphavantage.co/query?{params}"))
    except Exception as e:
        logger.warning(f"Alpha Vantage 抓取失败 {symbol}: {e}")
        return f"标的 {symbol}：Alpha Vantage 抓取失败（{e}）。"

    series = data.get('Time Series (Daily)')
    if not series:
        note = data.get('Note') or data.get('Information') or data.get('Error Message') or '无数据'
        return f"标的 {symbol}：Alpha Vantage 未返回行情（{note}）。"

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
    从 FRED 抓取宏观经济时间序列（需 API Key）。

    Args:
        series_id: FRED 序列代码，如 'CPIAUCSL'（CPI）、'FEDFUNDS'（联邦基金利率）、'UNRATE'（失业率）
    """
    lookback = lookback or Config.MARKET_DATA_DEFAULT_LOOKBACK
    if not Config.FRED_API_KEY:
        return f"宏观指标 {series_id}：未配置 FRED_API_KEY，已跳过 FRED 数据源。"

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
        logger.warning(f"FRED 抓取失败 {series_id}: {e}")
        return f"宏观指标 {series_id}：FRED 抓取失败（{e}）。"

    obs = list(reversed(data.get('observations', [])))  # 转为时间正序
    if not obs:
        return f"宏观指标 {series_id}：FRED 未返回数据。"
    points = [(o.get('date', ''), o.get('value')) for o in obs]
    return _summarize_series(f"宏观指标（FRED）：{series_id}", points, lookback)


def fetch_oecd(dataflow_query: str, lookback: int = None) -> str:
    """
    从 OECD SDMX-JSON 接口抓取宏观经济时间序列（免费、无需密钥）。

    Args:
        dataflow_query: SDMX 数据查询路径，形如
            'OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA,1.0/Q..USA...G1.'
            可在 OECD Data Explorer 中"开发者 API"处复制
        lookback: 取最近 N 个观测点
    """
    lookback = lookback or Config.MARKET_DATA_DEFAULT_LOOKBACK
    params = urllib.parse.urlencode({'format': 'jsondata', 'dimensionAtObservation': 'AllDimensions'})
    url = f"{Config.OECD_SDMX_BASE_URL}{dataflow_query}?{params}"
    try:
        data = json.loads(_http_get(url))
    except Exception as e:
        logger.warning(f"OECD 抓取失败 {dataflow_query}: {e}")
        return f"OECD 指标 {dataflow_query}：抓取失败（{e}）。"

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
        logger.warning(f"OECD 解析失败 {dataflow_query}: {e}")
        return f"OECD 指标 {dataflow_query}：数据解析失败（{e}）。"

    if not points:
        return f"OECD 指标 {dataflow_query}：未返回观测数据。"
    return _summarize_series(f"宏观指标（OECD）：{dataflow_query}", points, lookback)


def fetch_ecos(stat_code: str, item_code: str = '', cycle: str = 'M',
               start: str = '', end: str = '', count: int = 100) -> str:
    """
    从韩国银行 ECOS 接口抓取韩国宏观经济统计（需 ECOS_API_KEY）。

    Args:
        stat_code: 统计表代码，如 '722Y001'（基准利率）、'901Y009'（消费者物价指数）
        item_code: 统计项目代码（部分统计表必填）
        cycle: 周期，'D' 日 / 'M' 月 / 'Q' 季 / 'A' 年
        start, end: 起止时间，按周期格式（月 'YYYYMM'、年 'YYYY'、日 'YYYYMMDD'）
        count: 最大返回条数
    """
    if not Config.ECOS_API_KEY:
        return f"韩国宏观指标 {stat_code}：未配置 ECOS_API_KEY，已跳过 ECOS 数据源。"

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
        logger.warning(f"ECOS 抓取失败 {stat_code}: {e}")
        return f"韩国宏观指标 {stat_code}：ECOS 抓取失败（{e}）。"

    if 'RESULT' in data:
        msg = data['RESULT'].get('MESSAGE', '查询失败')
        return f"韩国宏观指标 {stat_code}：ECOS 返回错误（{msg}）。"

    rows = (data.get('StatisticSearch') or {}).get('row') or []
    if not rows:
        return f"韩国宏观指标 {stat_code}：ECOS 未返回数据。"

    title = rows[0].get('STAT_NAME', stat_code)
    item_name = rows[0].get('ITEM_NAME1', '')
    points = [(r.get('TIME', ''), r.get('DATA_VALUE')) for r in rows]
    points.sort(key=lambda p: p[0])
    label = f"韩国宏观指标（ECOS）：{title}" + (f" - {item_name}" if item_name else "")
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
    构建综合性的"市场种子文本"，作为模拟的现实数据输入。

    Args:
        stocks: 标的代码列表，格式取决于 stock_source
        stock_source: 行情数据源，'stooq' / 'yahoo' / 'alpha_vantage'
        fred_series: FRED 宏观序列代码列表（如 ['FEDFUNDS', 'CPIAUCSL']）
        oecd_queries: OECD SDMX 数据查询路径列表
        ecos_series: 韩国银行 ECOS 查询列表，元素可为统计表代码字符串，
                     或 dict（含 stat_code / item_code / cycle / start / end / count）
        lookback: 取最近 N 个交易日/观测点

    Returns:
        拼接后的市场种子文本，可直接作为文档输入图谱构建流程
    """
    sections = ["# 金融市场数据种子",
                "本文档由真实市场数据自动生成，用于驱动金融市场预测模拟。", ""]

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
        sections.append("（未指定任何标的或宏观指标）")

    return "\n".join(sections)
