"""
文件解析工具
支持PDF、Markdown、TXT文件的文本提取
"""

import os
from pathlib import Path
from typing import List, Optional


def _read_text_with_fallback(file_path: str) -> str:
    """
    读取文本文件，UTF-8失败时自动探测编码。
    
    采用多级回退策略：
    1. 首先尝试 UTF-8 解码
    2. 使用 charset_normalizer 检测编码
    3. 回退到 chardet 检测编码
    4. 最终使用 UTF-8 + errors='replace' 兜底
    
    Args:
        file_path: 文件路径
        
    Returns:
        解码后的文本内容
    """
    data = Path(file_path).read_bytes()
    
    # 首先尝试 UTF-8
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        pass
    
    # 尝试使用 charset_normalizer 检测编码
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass
    
    # 回退到 chardet
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass
    
    # 最终兜底：使用 UTF-8 + replace
    if not encoding:
        encoding = 'utf-8'
    
    return data.decode(encoding, errors='replace')


class FileParser:
    """文件解析器"""

    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt', '.csv'}
    
    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
        从文件中提取文本
        
        Args:
            file_path: 文件路径
            
        Returns:
            提取的文本内容
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        suffix = path.suffix.lower()
        
        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持的文件格式: {suffix}")
        
        if suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        elif suffix == '.txt':
            return cls._extract_from_txt(file_path)
        elif suffix == '.csv':
            return cls._extract_from_csv(file_path)

        raise ValueError(f"无法处理的文件格式: {suffix}")
    
    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """从PDF提取文本"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("需要安装PyMuPDF: pip install PyMuPDF")
        
        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
        
        return "\n\n".join(text_parts)
    
    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        """从Markdown提取文本，支持自动编码检测"""
        return _read_text_with_fallback(file_path)
    
    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        """从TXT提取文本，支持自动编码检测"""
        return _read_text_with_fallback(file_path)

    @staticmethod
    def _extract_from_csv(file_path: str) -> str:
        """
        CSV에서 텍스트를 추출하며, 금융 시세 데이터(OHLCV)는 가독성 있게 처리한다.

        표 데이터를 자연어 요약문으로 변환해 LLM이 시장 흐름을 이해하기 쉽게 한다.
        흔한 열 이름(Date/Open/High/Low/Close/Volume)을 인식해 등락률,
        기간 고저점 등 파생 설명을 생성한다. 시세가 아닌 CSV는 일반 표로 행마다 옮겨 적는다.
        """
        import csv
        import io

        raw = _read_text_with_fallback(file_path)
        reader = csv.reader(io.StringIO(raw))
        rows = [r for r in reader if any(cell.strip() for cell in r)]
        if not rows:
            return ""

        header = [h.strip() for h in rows[0]]
        data_rows = rows[1:]
        lower = [h.lower() for h in header]

        def col(*names):
            for n in names:
                if n in lower:
                    return lower.index(n)
            return None

        idx_date = col('date', 'datetime', 'time', '日期', '날짜', '일자')
        idx_close = col('close', 'adj close', 'adj_close', '收盘', '收盘价', '종가')

        lines = [f"CSV 시장 데이터, 총 {len(data_rows)}행, 열: {', '.join(header)}"]

        if idx_close is not None:
            idx_open = col('open', '开盘', '开盘价', '시가')
            idx_high = col('high', '最高', '最高价', '고가')
            idx_low = col('low', '最低', '最低价', '저가')
            idx_vol = col('volume', 'vol', '成交量', '거래량')

            def fnum(row, i):
                if i is None or i >= len(row):
                    return None
                try:
                    return float(str(row[i]).replace(',', '').strip())
                except (ValueError, AttributeError):
                    return None

            closes = [(r, fnum(r, idx_close)) for r in data_rows]
            closes = [(r, c) for r, c in closes if c is not None]
            if closes:
                first_c = closes[0][1]
                last_c = closes[-1][1]
                highs = [fnum(r, idx_high) for r, _ in closes]
                lows = [fnum(r, idx_low) for r, _ in closes]
                period_high = max([h for h in highs if h is not None] or [c for _, c in closes])
                period_low = min([l for l in lows if l is not None] or [c for _, c in closes])
                change_pct = ((last_c - first_c) / first_c * 100) if first_c else 0.0

                start_date = data_rows[0][idx_date].strip() if idx_date is not None and idx_date < len(data_rows[0]) else "시작"
                end_date = data_rows[-1][idx_date].strip() if idx_date is not None and idx_date < len(data_rows[-1]) else "종료"

                lines.append(
                    f"시세 개요: {start_date} ~ {end_date}, "
                    f"기간 종가가 {first_c:g}에서 {last_c:g}로 변동 (등락률 {change_pct:+.2f}%), "
                    f"기간 최고 {period_high:g}, 최저 {period_low:g}."
                )
                lines.append("일별 시세:")
                for row in data_rows:
                    parts = []
                    for label, i in (('날짜', idx_date), ('시가', idx_open), ('고가', idx_high),
                                     ('저가', idx_low), ('종가', idx_close), ('거래량', idx_vol)):
                        if i is not None and i < len(row) and str(row[i]).strip():
                            parts.append(f"{label} {str(row[i]).strip()}")
                    if parts:
                        lines.append("  " + ", ".join(parts))
                return "\n".join(lines)

        # 일반 표: 행마다 키-값 쌍으로 옮겨 적음
        for row in data_rows:
            pairs = [f"{header[i]}: {row[i].strip()}"
                     for i in range(min(len(header), len(row))) if row[i].strip()]
            if pairs:
                lines.append("  " + "; ".join(pairs))
        return "\n".join(lines)
    
    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        """
        从多个文件提取文本并合并
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            合并后的文本
        """
        all_texts = []
        
        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"=== 文档 {i}: {filename} ===\n{text}")
            except Exception as e:
                all_texts.append(f"=== 文档 {i}: {file_path} (提取失败: {str(e)}) ===")
        
        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str, 
    chunk_size: int = 500, 
    overlap: int = 50
) -> List[str]:
    """
    将文本分割成小块
    
    Args:
        text: 原始文本
        chunk_size: 每块的字符数
        overlap: 重叠字符数
        
    Returns:
        文本块列表
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # 尝试在句子边界处分割
        if end < len(text):
            # 查找最近的句子结束符
            for sep in ['。', '！', '？', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # 下一个块从重叠位置开始
        start = end - overlap if end < len(text) else len(text)
    
    return chunks

