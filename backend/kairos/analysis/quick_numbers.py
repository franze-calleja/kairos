import json
from pathlib import Path
from typing import Any, Literal

from kairos.models import Holding, QuickNumbers

SECTOR_PE_PATH = Path(__file__).parent.parent / "data" / "sector_pe.json"


def kind_from_info(info: dict[str, Any]) -> Literal["stock", "etf"]:
    return "etf" if str(info.get("quoteType", "")).upper() == "ETF" else "stock"


def sector_pe_reference(sector: str | None, path: Path = SECTOR_PE_PATH) -> float | None:
    if not sector or not path.exists():
        return None
    value = json.loads(path.read_text()).get("sectors", {}).get(sector)
    return float(value) if value is not None else None


def _num(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except TypeError, ValueError:
        return None


def build_quick_numbers(
    kind: Literal["stock", "etf"],
    info: dict[str, Any],
    holdings: list[Holding],
    fund: dict[str, float | None],
    sector_pe: float | None,
) -> QuickNumbers:
    if kind == "etf":
        info_expense = _num(info.get("netExpenseRatio"))
        return QuickNumbers(
            kind="etf",
            expense_ratio=fund.get("expense_ratio")
            or (info_expense / 100 if info_expense is not None else None),
            aum=_num(info.get("totalAssets")),
            top_holdings=holdings,
        )
    return QuickNumbers(
        kind="stock",
        market_cap=_num(info.get("marketCap")),
        trailing_pe=_num(info.get("trailingPE")),
        forward_pe=_num(info.get("forwardPE")),
        sector=info.get("sector"),
        sector_pe=sector_pe,
        revenue_growth=_num(info.get("revenueGrowth")),
        profit_margin=_num(info.get("profitMargins")),
    )
