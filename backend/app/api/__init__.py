"""
API 라우트 모듈
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)

from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401

# 시장 시뮬레이션 블루프린트 (별도 prefix 사용)
from .market_simulation import market_bp  # noqa: E402, F401

