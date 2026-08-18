from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from .logging_utils import TradeLogger
from .config import Settings


DEFAULT_TOP_SYMBOLS = ("AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA")
WATCHLIST_OPTIONS = ("AMD", "PLTR", "AVGO", "NFLX", "COST", "JPM", "COIN", "TSM")
THAI_MONTHS = (
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
)


def thai_today() -> str:
    today = datetime.now(ZoneInfo("Asia/Bangkok"))
    return f"{today.day} {THAI_MONTHS[today.month - 1]} {today.year + 543}"


def _display_action(action: str) -> str:
    return {"BUY": "ซื้อ", "HOLD": "ถือ/รอดู", "SELL": "ขาย"}.get(action, action)


def _display_reason(reason: str) -> str:
    if reason.startswith("support is ") and reason.endswith(" below current price; wait for a new base"):
        distance = reason.removeprefix("support is ").removesuffix(" below current price; wait for a new base")
        return f"แนวรับอยู่ต่ำกว่าราคาปัจจุบัน {distance} — รอให้ราคาสร้างฐานใหม่"
    translations = {
        "bullish bounce near clustered support": "เด้งจากแนวรับที่มีการทดสอบหลายครั้ง",
        "resistance breakout with volume confirmation": "ทะลุแนวต้านพร้อมปริมาณซื้อขายยืนยัน",
        "no qualified swing setup": "ยังไม่พบจังหวะ Swing ที่ผ่านเงื่อนไข",
        "insufficient support/resistance levels": "ข้อมูลแนวรับ/แนวต้านยังไม่เพียงพอ",
        "historical price bars are stale; support/resistance hidden": "ข้อมูลแท่งย้อนหลังยังไม่ล่าสุด จึงซ่อนแนวรับ/แนวต้านไว้",
        "close reached stop-loss": "ราคาปิดแตะจุดตัดขาดทุน",
        "close reached take-profit/resistance": "ราคาปิดแตะเป้าหมาย/แนวต้าน",
        "position is open; no exit condition": "มีสถานะเปิดอยู่ แต่ยังไม่พบเงื่อนไขขาย",
    }
    return translations.get(reason, reason)


WATCHLIST_PATH = Path("data/watchlist.json")


def _load_watchlist(default: tuple[str, ...]) -> tuple[str, ...]:
    if not WATCHLIST_PATH.exists():
        return default
    try:
        values = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
        return tuple(dict.fromkeys(str(value).strip().upper() for value in values if str(value).strip()))
    except (OSError, ValueError, TypeError):
        return default


def _save_watchlist(raw_value: str) -> tuple[str, ...]:
    symbols = tuple(dict.fromkeys(
        symbol.upper()
        for symbol in (part.strip() for part in raw_value.split(","))
        if re.fullmatch(r"[A-Z0-9.]{1,10}", symbol)
    ))
    if not symbols:
        raise ValueError("กรุณาระบุ ticker อย่างน้อย 1 ตัว เช่น AAPL, MSFT")
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PATH.write_text(json.dumps(symbols, ensure_ascii=False, indent=2), encoding="utf-8")
    return symbols


def _ticker_with_company(symbol: str, company_names: dict[str, str]) -> str:
    company_name = company_names.get(str(symbol).upper(), "")
    return f"{str(symbol).upper()} — {company_name}" if company_name else str(symbol).upper()


def _company_name(symbol: str, company_names: dict[str, str]) -> str:
    return company_names.get(str(symbol).upper(), "")


def _format_base_zone(zone) -> str:
    if not zone:
        return "—"
    return f"{zone[0]:,.2f}–{zone[1]:,.2f}"


def _signal_badge_color(action: str) -> str:
    return {"BUY": "green", "HOLD": "orange", "SELL": "red"}.get(action, "blue")


def _refresh_interval_label(seconds: int) -> str:
    if seconds == 60:
        return "1 นาที"
    if seconds % 60 == 0:
        return f"{seconds // 60} นาที"
    return f"{seconds} วินาที"


def _render_recommendation_cards(st, items: list[dict], company_names: dict[str, str], section_key: str) -> None:
    """Render real stock data in a Three.js-enhanced mobile swipe deck."""
    if not items:
        return
    from .interactive_cards import stock_card_deck

    def price(value) -> str:
        return f"${value:,.2f}" if value is not None else "—"

    deck_items = [
        {
            "symbol": item["symbol"],
            "company": _company_name(item["symbol"], company_names),
            "action": _display_action(item["action"]),
            "actionClass": item["action"].lower(),
            "price": price(item.get("price")),
            "base": _format_base_zone(item.get("suggested_base_zone")),
            "support": price(item.get("support")),
            "resistance": price(item.get("resistance")),
            "reason": _display_reason(item["reason"]),
        }
        for item in items
    ]
    st.caption(f"การ์ดทั้งหมด {len(deck_items)} ตัว — ใช้นิ้วปัดซ้าย–ขวาเพื่อเปลี่ยนหุ้น")
    stock_card_deck(deck_items, key=f"threejs-deck-{section_key}")


def run_dashboard(log_path: str = "data/trades.jsonl") -> None:
    try:
        import streamlit as st
    except ImportError as exc:
        raise RuntimeError("Install the dashboard dependency with: pip install -e '.[dashboard]'") from exc
    try:
        settings = Settings.from_env()
        config_error = None
    except ValueError as exc:
        settings = None
        config_error = str(exc)

    logger = TradeLogger(log_path)
    watchlist = _load_watchlist(("WDC",) if settings else ())
    st.set_page_config(page_title="ระบบวิเคราะห์หุ้นสหรัฐ", page_icon=":material/query_stats:", layout="wide")
    from .interactive_cards import stock_pulse_hero
    scan_from_toolbar = st.button(
        "รีเฟรชหุ้น",
        key="header_refresh",
        type="primary",
        icon=":material/refresh:",
        disabled=not settings,
    )
    st.html("""
    <style>
      .st-key-header_refresh { display: none !important; }
      #stock-pulse-header-refresh {
        position: absolute; top: 12px; right: 48px; z-index: 1000000; border: 1px solid rgba(153,246,228,.56);
        border-radius: 999px; padding: 8px 13px; cursor: pointer; color: #042f2e;
        background: linear-gradient(135deg,#99f6e4,#2dd4bf); box-shadow: 0 8px 20px rgba(20,184,166,.28);
        font: 800 12px/1 Inter, sans-serif;
      }
      #stock-pulse-header-refresh:hover { filter: brightness(1.06); transform: translateY(-1px); }
      #stock-pulse-header-refresh:disabled { opacity: .5; cursor: not-allowed; transform: none; }
      @media (max-width: 520px) { #stock-pulse-header-refresh { top: 11px; right: 44px; padding: 7px 10px; font-size: 11px; } }
    </style>
    <script>
      (() => {
        const mountRefresh = () => {
          const header = document.querySelector('[data-testid="stHeader"]');
          const nativeButton = document.querySelector('.st-key-header_refresh button');
          if (!header || !nativeButton) return;
          header.querySelectorAll('button').forEach((button) => {
            if (button.textContent.trim() === 'Deploy') button.style.display = 'none';
          });
          let refreshButton = document.getElementById('stock-pulse-header-refresh');
          if (!refreshButton) {
            refreshButton = document.createElement('button');
            refreshButton.id = 'stock-pulse-header-refresh';
            refreshButton.type = 'button';
            refreshButton.textContent = '↻  รีเฟรชหุ้น';
            refreshButton.setAttribute('aria-label', 'รีเฟรชข้อมูลหุ้น');
            header.appendChild(refreshButton);
          }
          refreshButton.disabled = nativeButton.disabled;
          refreshButton.onclick = () => nativeButton.click();
        };
        mountRefresh();
        window.clearInterval(window.stockPulseToolbarTimer);
        window.stockPulseToolbarTimer = window.setInterval(mountRefresh, 700);
      })();
    </script>
    """, unsafe_allow_javascript=True)
    scan_from_main = scan_from_toolbar or stock_pulse_hero(ready=bool(settings))

    @st.cache_data(ttl="6h", max_entries=1, show_spinner=False)
    def load_company_directory(_settings) -> tuple[tuple[str, str], ...]:
        """Load active US equities once, without persisting credentials."""
        from alpaca.trading.client import TradingClient
        from alpaca.trading.enums import AssetClass, AssetStatus
        from alpaca.trading.requests import GetAssetsRequest

        client = TradingClient(_settings.alpaca_api_key, _settings.alpaca_secret_key, paper=True)
        assets = client.get_all_assets(GetAssetsRequest(status=AssetStatus.ACTIVE, asset_class=AssetClass.US_EQUITY))
        return tuple(sorted(
            (asset.symbol.upper(), str(asset.name).strip())
            for asset in assets
            if asset.tradable and asset.symbol and asset.name
        ))

    @st.cache_data(ttl="1h", max_entries=1, show_spinner=False)
    def load_daily_recommendations(universe_symbols: tuple[str, ...], _settings) -> list[dict]:
        from .broker import AlpacaPaperBroker
        from .market_data import AlpacaMarketDataAdapter
        from .paper_engine import PaperTradingEngine

        market_data = AlpacaMarketDataAdapter(_settings)
        liquid_symbols = market_data.most_liquid_symbols(universe_symbols, limit=50)
        engine = PaperTradingEngine(_settings, market_data, AlpacaPaperBroker(_settings), logger)
        return _rank_recommendations(engine.scan_many_realtime(liquid_symbols))[:5]

    @st.cache_data(max_entries=1, show_spinner=False)
    def load_day_trade_recommendations(symbols: tuple[str, ...], _settings) -> list[dict]:
        """Evaluate the seven core stocks on recent 5-minute bars."""
        from .broker import AlpacaPaperBroker
        from .market_data import AlpacaMarketDataAdapter
        from .paper_engine import PaperTradingEngine

        market_data = AlpacaMarketDataAdapter(_settings, timeframe="5Min")
        engine = PaperTradingEngine(_settings, market_data, AlpacaPaperBroker(_settings), logger)
        return _rank_recommendations(engine.scan_many_realtime(symbols))

    company_names: dict[str, str] = {}
    if settings:
        try:
            company_names = dict(load_company_directory(settings))
        except Exception as exc:
            st.warning(f"โหลดรายชื่อบริษัทจาก Alpaca ไม่สำเร็จ: {exc}")

    with st.sidebar:
        st.header(":material/query_stats: สแกนหุ้นเด่น")
        st.caption("จัดอันดับจากข้อมูลล่าสุด — ไม่ส่งคำสั่งซื้อขาย")
        if settings:
            # Keep this section strictly to the seven Magnificent Seven stocks.
            # User watchlist symbols must never replace one of these seven cards.
            scan_symbols = DEFAULT_TOP_SYMBOLS
            st.caption("หุ้นที่สแกน: " + ", ".join(scan_symbols))
            st.caption("กดปุ่มรีเฟรชด้านบนเมื่อต้องการข้อมูลล่าสุด")
            scan_clicked = False
        else:
            st.error(config_error or "Invalid configuration")
            st.info("ตรวจสอบไฟล์ .env และตั้ง ALPACA_PAPER=true")
            scan_symbols = ()
            scan_clicked = False

    def refresh_realtime(record_signal: bool = False):
        from .broker import AlpacaPaperBroker
        from .market_data import AlpacaMarketDataAdapter
        from .paper_engine import PaperTradingEngine

        market_data = AlpacaMarketDataAdapter(settings)
        broker = AlpacaPaperBroker(settings)
        engine = PaperTradingEngine(settings, market_data, broker, logger)
        results = []
        failures = []
        scan_universe = tuple(dict.fromkeys((*scan_symbols, *watchlist)))
        for candidate in scan_universe:
            try:
                results.append(engine.scan_realtime(candidate, record_signal=record_signal))
            except Exception as exc:
                failures.append(f"{candidate}: {exc}")
        top_results = [item for item in results if item["symbol"] in scan_symbols]
        watch_results = [item for item in results if item["symbol"] in watchlist]
        st.session_state["top_recommendations"] = _rank_recommendations(top_results)
        st.session_state["watch_recommendations"] = _rank_recommendations(watch_results)
        st.session_state["scan_failures"] = failures

    if (scan_clicked or scan_from_main) and settings and scan_symbols:
        st.session_state["manual_scan_requested"] = True

    def render_realtime_panel():
        if settings and scan_symbols:
            try:
                manual_scan_requested = st.session_state.pop("manual_scan_requested", False)
                if manual_scan_requested:
                    # Keep the daily picks dynamic: a manual refresh deliberately
                    # bypasses the hourly cache and ranks the market again.
                    load_daily_recommendations.clear()
                    load_day_trade_recommendations.clear()
                    with st.spinner("กำลังสแกน Top 7..."):
                        refresh_realtime(record_signal=True)
                    st.success("สแกน Top 7 สำเร็จ — ไม่มีการส่งคำสั่ง")
                elif "top_recommendations" not in st.session_state:
                    refresh_realtime(record_signal=False)
            except Exception as exc:
                st.error(f"ดึงข้อมูล real-time ไม่สำเร็จ: {exc}")

        recommendations = st.session_state.get("top_recommendations", [])
        if recommendations:
            active_view = st.segmented_control(
                "เลือกหมวดหุ้น",
                options=("หุ้นนางฟ้า", "หุ้นน่าซื้อ", "Day Trade", "หุ้นที่เล็งไว้"),
                default="หุ้นนางฟ้า",
                selection_mode="single",
                required=True,
                label_visibility="collapsed",
                width="stretch",
                key="mobile_stock_view",
            )

            if active_view == "หุ้นนางฟ้า":
                st.subheader("หุ้นนางฟ้า 7 อันดับ")
                _render_recommendation_cards(st, recommendations, company_names, "top")
            elif active_view == "หุ้นน่าซื้อ":
                st.subheader(f"หุ้นน่าซื้อประจำวัน — {thai_today()}")
                st.caption("สแกนหุ้นสหรัฐทั้งหมดที่ Alpaca รองรับ → คัดสภาพคล่องสูง → วิเคราะห์ 50 ตัว → แนะนำ 5 ตัว • อัปเดตทุก 1 ชั่วโมง หรือกดรีเฟรชเพื่อคัดใหม่ทันที")
                try:
                    daily_recommendations = load_daily_recommendations(tuple(company_names), settings)
                    if daily_recommendations:
                        _render_recommendation_cards(st, daily_recommendations, company_names, "daily")
                    else:
                        st.info("ยังไม่พบหุ้นที่มีข้อมูลเพียงพอสำหรับการจัดอันดับ")
                except Exception as exc:
                    st.warning(f"สแกนหุ้นน่าซื้อรายชั่วโมงไม่สำเร็จ: {exc}")
            elif active_view == "Day Trade":
                st.subheader("Day Trade — แนวรับ แนวต้าน")
                st.caption("วิเคราะห์แท่งราคา 5 นาทีของหุ้น 7 นางฟ้า • กดรีเฟรชเพื่ออัปเดต • Paper Trading เท่านั้น")
                try:
                    day_trade_recommendations = load_day_trade_recommendations(DEFAULT_TOP_SYMBOLS, settings)
                    if day_trade_recommendations:
                        _render_recommendation_cards(st, day_trade_recommendations, company_names, "day-trade")
                    else:
                        st.info("ยังไม่มีข้อมูลแท่งราคา 5 นาทีเพียงพอสำหรับ Day Trade")
                except Exception as exc:
                    st.warning(f"โหลดข้อมูล Day Trade ไม่สำเร็จ: {exc}")
            else:
                st.subheader("หุ้นที่เล็งไว้")
                watchlist_options = tuple(sorted(dict.fromkeys(
                    (*company_names, *DEFAULT_TOP_SYMBOLS, *WATCHLIST_OPTIONS, *settings.symbols, *watchlist)
                )))
                st.caption(f"เลือกได้จากหุ้นสหรัฐที่ Alpaca รองรับ {len(company_names):,} ตัว หรือพิมพ์ ticker ใหม่เอง")
                selected_watchlist = st.multiselect(
                    "พิมพ์ค้นหา ticker แล้วเลือกจากรายการ",
                    options=watchlist_options,
                    default=[symbol for symbol in watchlist if symbol in watchlist_options],
                    format_func=lambda symbol: _ticker_with_company(str(symbol), company_names),
                    accept_new_options=True,
                    help="เลือกจากรายการ หรือพิมพ์ ticker ใหม่ เช่น WDC แล้วกด Enter ได้เลย",
                    placeholder="เช่น AAPL หรือ Apple",
                    key="watchlist_ticker_search",
                )
                if st.button("บันทึกรายการที่เล็งไว้", key="save_main_watchlist"):
                    try:
                        _save_watchlist(",".join(selected_watchlist))
                        # The rerun below reloads the saved list. Request a scan so the
                        # watchlist panel contains fresh cards instead of an empty state.
                        st.session_state["manual_scan_requested"] = True
                        st.success("บันทึกแล้ว — กำลังสแกนหุ้นที่เล็งไว้")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                watch_recommendations = st.session_state.get("watch_recommendations", [])
                if watch_recommendations:
                    _render_recommendation_cards(st, watch_recommendations, company_names, "watch")
                else:
                    st.info("ยังไม่มีข้อมูลของหุ้นที่เล็งไว้ กดสแกนเพื่ออัปเดต")
            failures = st.session_state.get("scan_failures", [])
            if failures:
                st.warning("บาง symbol สแกนไม่สำเร็จ: " + "; ".join(failures))
        else:
            st.info("ยังไม่มีข้อมูลสแกน กด **รีเฟรชข้อมูลหุ้น** ด้านบนเพื่อเริ่มต้น")

    render_realtime_panel()

def _rank_recommendations(results: list[dict]) -> list[dict]:
    """Put executable BUY setups first, then rank by signal confidence."""
    action_rank = {"BUY": 2, "HOLD": 1, "SELL": 0}
    return sorted(results, key=lambda item: (action_rank.get(item["action"], 0), item["score"]), reverse=True)[:7]


def _recommendation_rows(items: list[dict], company_names: dict[str, str] | None = None) -> list[dict]:
    company_names = company_names or {}
    return [
        {
            "อันดับ": index,
            "หุ้น": _ticker_with_company(item["symbol"], company_names),
            "สัญญาณ": _display_action(item["action"]),
            "คะแนน": round(item["score"], 1),
            "ราคาปัจจุบัน": round(item["price"], 2),
            "โซนฐานใหม่ที่รอ": _format_base_zone(item.get("suggested_base_zone")),
            "สถานะแนวรับ/ต้าน": "พร้อมใช้" if item.get("levels_status", "current") == "current" else "รอข้อมูลย้อนหลังล่าสุด",
            "แนวรับ": round(item["support"], 2) if item["support"] is not None else "—",
            "แนวต้าน": round(item["resistance"], 2) if item["resistance"] is not None else "—",
            "เหตุผล": _display_reason(item["reason"]),
        }
        for index, item in enumerate(items, start=1)
    ]


if __name__ == "__main__":
    run_dashboard()
