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
WATCHLIST_TIMEFRAME_OPTIONS = (("1 วัน", "1Day"), ("8 ชั่วโมง", "8Hour"), ("4 ชั่วโมง", "4Hour"), ("1 ชั่วโมง", "1Hour"), ("5 นาที", "5Min"))
WATCHLIST_TIMEFRAME_LABELS = tuple(label for label, _ in WATCHLIST_TIMEFRAME_OPTIONS)
WATCHLIST_TIMEFRAME_CODES = dict(WATCHLIST_TIMEFRAME_OPTIONS)
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
      :root, body, [data-testid="stAppViewContainer"] { background: var(--st-background-color, #f7fbff) !important; }
      [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(circle at 8% 0%, color-mix(in srgb, var(--st-primary-color, #14b8a6) 16%, transparent), transparent 34%),
          radial-gradient(circle at 96% 18%, color-mix(in srgb, var(--st-blue-color, #60a5fa) 12%, transparent), transparent 30%),
          linear-gradient(180deg, var(--st-background-color, #fbfeff) 0%, var(--st-secondary-background-color, #eaf5f8) 100%) !important;
      }
      [data-testid="stHeader"] { background: transparent !important; }
      [data-testid="stMain"] { background: transparent !important; color: var(--st-text-color, #10233f) !important; }
      [data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3,
      [data-testid="stMain"] h4, [data-testid="stMain"] p, [data-testid="stMain"] label { color: var(--st-text-color, #10233f) !important; }
      [data-testid="stMain"] [data-testid="stCaptionContainer"] { color: var(--st-secondary-text-color, #5d7188) !important; }
      [data-testid="stSegmentedControl"] button {
        color: #ffffff !important; background: #10233f !important; border-color: #6f8da5 !important;
        text-shadow: none !important;
      }
      [data-testid="stSegmentedControl"] button *,
      [data-testid="stSegmentedControlOption"],
      [data-testid="stSegmentedControlOption"] * {
        color: #ffffff !important; text-shadow: none !important;
      }
      [data-testid="stSegmentedControl"] button[aria-pressed="true"] {
        color: #073b3b !important; background: #b9f3e9 !important; border-color: #14b8a6 !important;
      }
      [data-testid="stSegmentedControl"] button[aria-pressed="true"] *,
      [data-testid="stSegmentedControlOption"][aria-pressed="true"],
      [data-testid="stSegmentedControlOption"][aria-pressed="true"] * {
        color: #073b3b !important;
      }
      .st-key-mobile_stock_view button,
      .st-key-watchlist_timeframe_selector button { color: #ffffff !important; }
      .st-key-mobile_stock_view button[aria-pressed="true"],
      .st-key-watchlist_timeframe_selector button[aria-pressed="true"] { color: #073b3b !important; }
      .st-key-mobile_stock_view button[aria-pressed="true"] *,
      .st-key-watchlist_timeframe_selector button[aria-pressed="true"] * { color: #073b3b !important; }
      .st-key-mobile_stock_view [role="radio"],
      .st-key-watchlist_timeframe_selector [role="radio"] {
        color: #ffffff !important; background: #10233f !important; border-color: #6f8da5 !important;
      }
      .st-key-mobile_stock_view [role="radio"] *,
      .st-key-watchlist_timeframe_selector [role="radio"] * { color: #ffffff !important; }
      .st-key-mobile_stock_view [role="radio"][aria-checked="true"],
      .st-key-watchlist_timeframe_selector [role="radio"][aria-checked="true"] {
        color: #073b3b !important; background: #b9f3e9 !important; border-color: #14b8a6 !important;
      }
      .st-key-mobile_stock_view [role="radio"][aria-checked="true"] *,
      .st-key-watchlist_timeframe_selector [role="radio"][aria-checked="true"] * { color: #073b3b !important; }
      .st-key-save_main_watchlist button {
        color: #17324d !important; background: #e7f1f6 !important; border: 1px solid #8eafc2 !important;
        box-shadow: none !important;
      }
      .st-key-watchlist_ticker_search [data-baseweb="select"] {
        color: #17324d !important; background: #ffffff !important; border-color: #8eafc2 !important;
      }
      .st-key-watchlist_ticker_search input { color: #17324d !important; caret-color: #0f766e !important; }
      .st-key-watchlist_ticker_search [data-baseweb="tag"] {
        color: #073b3b !important; background: #b9f3e9 !important;
      }
      .st-key-watchlist_ticker_search [data-baseweb="tag"] svg { fill: #0f5f5a !important; }
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
    try:
        active_theme = st.context.theme.type
    except Exception:
        active_theme = "light"
    if active_theme == "dark":
        st.html("""
        <style>
          :root, body, [data-testid="stAppViewContainer"] { background: #071426 !important; }
          [data-testid="stAppViewContainer"] {
            background:
              radial-gradient(circle at 8% 0%, rgba(20,184,166,.16), transparent 34%),
              radial-gradient(circle at 96% 18%, rgba(96,165,250,.12), transparent 30%),
              linear-gradient(180deg, #071426 0%, #0b1428 100%) !important;
          }
          [data-testid="stMain"] { color: #e7eef9 !important; }
          [data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3,
          [data-testid="stMain"] h4, [data-testid="stMain"] p, [data-testid="stMain"] label { color: #e7eef9 !important; }
          [data-testid="stMain"] [data-testid="stCaptionContainer"] { color: #a8bad0 !important; }
          .st-key-save_main_watchlist button { color: #e7eef9 !important; background: #14213d !important; border-color: #40617d !important; }
          .st-key-watchlist_ticker_search [data-baseweb="select"] { color: #e7eef9 !important; background: #14213d !important; border-color: #40617d !important; }
          .st-key-watchlist_ticker_search input { color: #e7eef9 !important; }
        </style>
        """)
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
    def load_watchlist_recommendations(symbols: tuple[str, ...], timeframe: str, _settings) -> list[dict]:
        """Evaluate the watchlist with support/resistance from the selected bars."""
        from .broker import AlpacaPaperBroker
        from .market_data import AlpacaMarketDataAdapter
        from .paper_engine import PaperTradingEngine

        market_data = AlpacaMarketDataAdapter(_settings, timeframe=timeframe)
        engine = PaperTradingEngine(_settings, market_data, AlpacaPaperBroker(_settings), logger)
        return _rank_recommendations(engine.scan_many_realtime(symbols), limit=None)

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

    def refresh_watchlist_on_timeframe_change() -> None:
        """Treat a timeframe selection like the main refresh action."""
        st.session_state["manual_scan_requested"] = True

    def refresh_realtime(record_signal: bool = False):
        from .broker import AlpacaPaperBroker
        from .market_data import AlpacaMarketDataAdapter
        from .paper_engine import PaperTradingEngine

        market_data = AlpacaMarketDataAdapter(settings)
        broker = AlpacaPaperBroker(settings)
        engine = PaperTradingEngine(settings, market_data, broker, logger)
        results = []
        failures = []
        for candidate in scan_symbols:
            try:
                results.append(engine.scan_realtime(candidate, record_signal=record_signal))
            except Exception as exc:
                failures.append(f"{candidate}: {exc}")
        top_results = [item for item in results if item["symbol"] in scan_symbols]
        watch_results = []
        watchlist_timeframe = WATCHLIST_TIMEFRAME_CODES.get(
            st.session_state.get("watchlist_timeframe_selector", "1 ชั่วโมง"),
            "1Hour",
        )
        if watchlist:
            try:
                watch_results = load_watchlist_recommendations(watchlist, watchlist_timeframe, settings)
            except Exception as exc:
                failures.append(f"watchlist: {exc}")
        st.session_state["top_recommendations"] = _rank_recommendations(top_results)
        st.session_state["watch_recommendations"] = watch_results
        st.session_state["watch_recommendations_timeframe"] = watchlist_timeframe
        st.session_state["scan_failures"] = failures

    if (scan_clicked or scan_from_main) and settings and scan_symbols:
        st.session_state["manual_scan_requested"] = True

    def render_realtime_panel():
        manual_scan_requested = False
        if settings and scan_symbols:
            try:
                manual_scan_requested = st.session_state.pop("manual_scan_requested", False)
                if manual_scan_requested:
                    # Keep the daily picks dynamic: a manual refresh deliberately
                    # bypasses the hourly cache and ranks the market again.
                    load_daily_recommendations.clear()
                    load_watchlist_recommendations.clear()
                    with st.spinner("กำลังสแกน Top 7..."):
                        refresh_realtime(record_signal=True)
                elif "top_recommendations" not in st.session_state:
                    refresh_realtime(record_signal=False)
            except Exception as exc:
                st.error(f"ดึงข้อมูล real-time ไม่สำเร็จ: {exc}")

        recommendations = st.session_state.get("top_recommendations", [])
        if recommendations:
            active_view = st.segmented_control(
                "เลือกหมวดหุ้น",
                options=("หุ้นนางฟ้า", "หุ้นน่าซื้อ", "หุ้นที่เล็งไว้"),
                default="หุ้นนางฟ้า",
                selection_mode="single",
                required=True,
                label_visibility="collapsed",
                width="stretch",
                key="mobile_stock_view",
            )
            if active_view not in {"หุ้นนางฟ้า", "หุ้นน่าซื้อ", "หุ้นที่เล็งไว้"}:
                active_view = "หุ้นนางฟ้า"

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
            else:
                st.subheader("หุ้นที่เล็งไว้")
                st.caption("ใช้รายการนี้สำหรับวิเคราะห์ Day Trade • กดช่วงเวลาเพื่อดึงแนวรับ–แนวต้านใหม่อัตโนมัติ")
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
                    _render_recommendation_cards(st, watch_recommendations, company_names, "watch-hourly")
                else:
                    st.info("ยังไม่มีข้อมูลของหุ้นที่เล็งไว้ กดสแกนเพื่ออัปเดต")
                st.caption("ช่วงเวลาแนวรับ–แนวต้าน")
                selected_timeframe_label = st.segmented_control(
                    "เลือกช่วงเวลา",
                    options=WATCHLIST_TIMEFRAME_LABELS,
                    default="1 ชั่วโมง",
                    selection_mode="single",
                    required=True,
                    label_visibility="collapsed",
                    width="stretch",
                    key="watchlist_timeframe_selector",
                    on_change=refresh_watchlist_on_timeframe_change,
                )
                loaded_timeframe = st.session_state.get("watch_recommendations_timeframe", "1Hour")
                if WATCHLIST_TIMEFRAME_CODES.get(selected_timeframe_label) != loaded_timeframe:
                    st.caption("เลือกช่วงเวลาแล้ว — กดรีเฟรชหุ้นเพื่อคำนวณแนวรับ–แนวต้านใหม่")
            failures = st.session_state.get("scan_failures", [])
            if failures:
                st.warning("บาง symbol สแกนไม่สำเร็จ: " + "; ".join(failures))
        else:
            st.info("ยังไม่มีข้อมูลสแกน กด **รีเฟรชข้อมูลหุ้น** ด้านบนเพื่อเริ่มต้น")

    render_realtime_panel()

def _rank_recommendations(results: list[dict], *, limit: int | None = 7) -> list[dict]:
    """Put executable BUY setups first, then rank by signal confidence."""
    action_rank = {"BUY": 2, "HOLD": 1, "SELL": 0}
    ranked = sorted(results, key=lambda item: (action_rank.get(item["action"], 0), item["score"]), reverse=True)
    return ranked if limit is None else ranked[:limit]


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
