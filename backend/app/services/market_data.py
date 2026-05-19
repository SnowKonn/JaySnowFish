"""
金融市场数据服务
从公开数据源抓取行情与宏观经济数据，转换为可用于模拟的"市场种子文本"。

支持的数据源：
- Stooq：免费、无需密钥，提供股票/指数/外汇/商品的日线历史行情
- Alpha Vantage：股票/外汇/加密货币行情（需 ALPHA_VANTAGE_API_KEY）
- FRED：美联储宏观经济数据（需 FRED_API_KEY）

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

    obs = [o for o in data.get('observations', []) if o.get('value') not in (None, '', '.')]
    if not obs:
        return f"宏观指标 {series_id}：FRED 未返回数据。"

    obs = list(reversed(obs))  # 转为时间正序
    try:
        first_v = float(obs[0]['value'])
        last_v = float(obs[-1]['value'])
        change_pct = ((last_v - first_v) / first_v * 100) if first_v else 0.0
    except (ValueError, KeyError):
        first_v = last_v = change_pct = 0.0

    lines = [
        f"## 宏观指标：{series_id}",
        f"区间：{obs[0]['date']} 至 {obs[-1]['date']}（共 {len(obs)} 个观测点）",
        f"数值自 {first_v:g} 变化至 {last_v:g}，区间变化 {change_pct:+.2f}%。",
        "近期观测：",
    ]
    for o in obs[-15:]:
        lines.append(f"  {o['date']}：{o['value']}")
    return "\n".join(lines)


def build_market_seed(
    stocks: Optional[List[str]] = None,
    fred_series: Optional[List[str]] = None,
    lookback: int = None,
    use_alpha_vantage: bool = False,
) -> str:
    """
    构建综合性的"市场种子文本"，作为模拟的现实数据输入。

    Args:
        stocks: 标的代码列表（Stooq 格式，如 ['aapl.us', '^spx']）
        fred_series: FRED 宏观序列代码列表（如 ['FEDFUNDS', 'CPIAUCSL']）
        lookback: 取最近 N 个交易日/观测点
        use_alpha_vantage: 为 True 时改用 Alpha Vantage 抓取股票行情

    Returns:
        拼接后的市场种子文本，可直接作为文档输入图谱构建流程
    """
    sections = ["# 金融市场数据种子",
                "本文档由真实市场数据自动生成，用于驱动金融市场预测模拟。", ""]

    for symbol in (stocks or []):
        if use_alpha_vantage:
            sections.append(fetch_alpha_vantage(symbol, lookback))
        else:
            sections.append(fetch_stooq(symbol, lookback))
        sections.append("")

    for series_id in (fred_series or []):
        sections.append(fetch_fred(series_id, lookback))
        sections.append("")

    if not stocks and not fred_series:
        sections.append("（未指定任何标的或宏观指标）")

    return "\n".join(sections)
