"""
파일 파싱 도구
PDF, Markdown, TXT 파일의 텍스트 추출 지원
"""

import os
from pathlib import Path
from typing import List, Optional


def _read_text_with_fallback(file_path: str) -> str:
    """
    텍스트 파일 읽기, UTF-8 실패 시 인코딩 자동 감지.

    다단계 폴백 전략:
    1. 먼저 UTF-8 디코딩 시도
    2. charset_normalizer로 인코딩 감지
    3. chardet로 인코딩 감지 폴백
    4. 최종적으로 UTF-8 + errors='replace' 사용

    Args:
        file_path: 파일 경로

    Returns:
        디코딩된 텍스트 내용
    """
    data = Path(file_path).read_bytes()

    # 먼저 UTF-8 시도
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        pass

    # charset_normalizer로 인코딩 감지 시도
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass

    # chardet로 폴백
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass

    # 최종 폴백: UTF-8 + replace 사용
    if not encoding:
        encoding = 'utf-8'

    return data.decode(encoding, errors='replace')


class FileParser:
    """파일 파서"""

    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt', '.csv'}

    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
        파일에서 텍스트 추출

        Args:
            file_path: 파일 경로

        Returns:
            추출된 텍스트 내용
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"파일이 존재하지 않습니다: {file_path}")

        suffix = path.suffix.lower()

        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"지원하지 않는 파일 형식: {suffix}")

        if suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        elif suffix == '.txt':
            return cls._extract_from_txt(file_path)
        elif suffix == '.csv':
            return cls._extract_from_csv(file_path)

        raise ValueError(f"처리할 수 없는 파일 형식: {suffix}")

    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """PDF에서 텍스트 추출"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("PyMuPDF 설치 필요: pip install PyMuPDF")

        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)

        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        """Markdown에서 텍스트 추출, 자동 인코딩 감지 지원"""
        return _read_text_with_fallback(file_path)

    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        """TXT에서 텍스트 추출, 자동 인코딩 감지 지원"""
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
        여러 파일에서 텍스트 추출 및 병합

        Args:
            file_paths: 파일 경로 목록

        Returns:
            병합된 텍스트
        """
        all_texts = []

        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"=== 문서 {i}: {filename} ===\n{text}")
            except Exception as e:
                all_texts.append(f"=== 문서 {i}: {file_path} (추출 실패: {str(e)}) ===")

        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> List[str]:
    """
    텍스트를 작은 청크로 분할

    Args:
        text: 원본 텍스트
        chunk_size: 청크당 문자 수
        overlap: 중복 문자 수

    Returns:
        텍스트 청크 목록
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # 문장 경계에서 분할 시도
        if end < len(text):
            # 가장 가까운 문장 종결자 찾기
            for sep in ['。', '！', '？', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # 다음 청크는 중복 위치에서 시작
        start = end - overlap if end < len(text) else len(text)

    return chunks
