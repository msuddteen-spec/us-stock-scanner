# US Paper Trading MVP

โปรเจกต์ Python สำหรับทดลอง swing trading หุ้นสหรัฐแบบ paper-only โดยแบ่งระบบเป็น market data adapter, support/resistance engine, signal engine, risk manager, position sizing, paper broker adapter, backtest และ dashboard/logging

> **ความปลอดภัย:** เวอร์ชันนี้ไม่เชื่อมต่อเงินจริงและไม่รองรับ live trading โดย `ALPACA_PAPER=false` จะถูกปฏิเสธ และ Alpaca adapter สร้าง `TradingClient(..., paper=True)` แบบตายตัว โปรเจกต์นี้เป็นซอฟต์แวร์ทดลอง ไม่ใช่คำแนะนำการลงทุน

## สิ่งที่มีใน MVP

- Alpaca historical market-data adapter ใช้ `IEX` เป็นค่าเริ่มต้น
- ดึงราคาล่าสุดเมื่อผู้ใช้กดปุ่มรีเฟรช เหมาะกับ swing trading ไม่ใช่ HFT
- แนวรับ/แนวต้านจาก clustered swing highs/lows และแสดงเป็นโซน
- สัญญาณ long-only: bullish support bounce หรือ resistance breakout ที่มี volume confirmation
- Risk guard: เสี่ยงต่อไม้, max position notional, max open positions, daily loss halt และห้าม average down
- Position sizing จากระยะ entry-to-stop
- Alpaca paper broker adapter และ in-memory simulated broker สำหรับ tests/backtest
- Backtest แบบ execute ที่แท่งถัดไปเพื่อหลีกเลี่ยง same-bar look-ahead
- JSONL trade/signal logging และ Streamlit dashboard

## ติดตั้ง

ต้องใช้ Python 3.11 ขึ้นไป

บน Windows สามารถดับเบิลคลิกไฟล์ `START_PAPER_TRADING.bat` ได้เลย ระบบจะสร้าง environment และเปิด dashboard ให้อัตโนมัติ ครั้งแรกจะใช้เวลาติดตั้ง dependencies สักครู่ จากนั้นแก้ไฟล์ `.env` ด้วย Alpaca Paper API keys หากต้องการใช้ market scan/order

```powershell
cd outputs/us-paper-trading-mvp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,alpaca,dashboard]"
```

สร้างไฟล์ `.env` จาก `.env.example` แล้วกรอก **Alpaca Paper Trading API keys เท่านั้น**:

```powershell
Copy-Item .env.example .env
```

ตัวแปรหลักคือ `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_PAPER=true`, `ALPACA_DATA_FEED=iex`, `SYMBOLS`, `TIMEFRAME`, `RISK_PER_TRADE_PCT`, `MAX_POSITION_PCT`, `MAX_DAILY_LOSS_PCT` และ `MAX_OPEN_POSITIONS` โปรเจกต์จะไม่อ่านหรือโหลด key จากไฟล์อื่น

ตรวจ config โดยไม่เชื่อมต่อ Alpaca:

```powershell
paper-trading check-config
```

Dashboard จะดึงราคาล่าสุดและคำนวณ signal/แนวรับ/แนวต้านของหุ้น 7 อันดับเมื่อเปิดหน้าเป็นครั้งแรก พร้อมหัวข้อหุ้นน่าซื้อประจำวันตามวันที่ไทย โดยไม่ส่งคำสั่งซื้อขาย หากต้องการข้อมูลใหม่ให้กดปุ่ม `รีเฟรชข้อมูลหุ้น`

ส่วน `หุ้นที่เล็งไว้` แก้ไขได้จากแท็บ `หุ้นที่เล็งไว้` โดยพิมพ์ค้นหา ticker ใน dropdown แล้วเลือกได้หลายตัว จากนั้นกด `บันทึกรายการที่เล็งไว้` รายการจะถูกเก็บไว้ใน `data/watchlist.json` และถูกสแกนแยกจากหุ้นนางฟ้า 7 อันดับ

สแกนข้อมูล Alpaca แบบ paper mode โดยยังไม่ส่งคำสั่ง:

```powershell
paper-trading paper-scan --symbol AAPL
```

เมื่อผ่านการตรวจสอบใน paper account แล้ว จึงค่อยใช้ `--execute` ซึ่งจะส่งเฉพาะ bracket order ที่มี stop-loss/take-profit ไปยัง Alpaca paper account:

```powershell
paper-trading paper-scan --symbol AAPL --execute
```

คำสั่งนี้เป็นการทำงานหนึ่งรอบ ไม่ใช่ daemon จึงหยุดได้ง่ายและเหมาะกับการตั้ง scheduler ภายหลัง

## ทดสอบ

```powershell
pytest
```

## Backtest จาก CSV

CSV ต้องมีคอลัมน์ `timestamp,open,high,low,close,volume` และเรียงตามเวลาได้ ระบบจะเรียงให้อัตโนมัติ:

```powershell
paper-trading backtest --csv data/AAPL.csv --symbol AAPL --cash 100000
```

ผลลัพธ์จะแสดง ending equity, return, จำนวน trades, max drawdown, win rate และ profit factor

## Dashboard

```powershell
streamlit run dashboard_app.py
```

หรือเรียกฟังก์ชัน `run_dashboard("data/trades.jsonl")` จากสคริปต์ของคุณเอง ไฟล์ log เป็น JSONL เพื่อให้ตรวจสอบเหตุผลของ signal และผลลัพธ์แต่ละ trade ได้

## เปิดใช้บนมือถือ (Streamlit Community Cloud)

1. นำโฟลเดอร์นี้ขึ้น GitHub โดยไม่ต้องอัปโหลดไฟล์ `.env`
2. ใน Streamlit Community Cloud เลือก repository และกำหนดไฟล์เริ่มต้นเป็น `dashboard_app.py`
3. ใน **Advanced settings → Secrets** เพิ่มค่าจาก `.env.example` โดยใช้ Alpaca **Paper** keys เท่านั้น
4. เปิด URL ที่ Streamlit Cloud สร้างจากมือถือได้ทันที

ไฟล์ `requirements.txt` ได้ตั้งค่าให้ติดตั้งส่วน dashboard และ Alpaca adapter แล้ว

## ขั้นต่อไปก่อนใช้เงินจริง

1. เพิ่มข้อมูล historical ที่มี corporate actions และตรวจสอบ timezone/market calendar
2. ทำ walk-forward test, slippage/commission model และ out-of-sample validation
3. รัน Alpaca paper account ต่อเนื่องโดยมี human approval ก่อนเปิด auto-submit
4. เพิ่ม reconciliation ระหว่าง fills จาก broker กับ local log และ kill switch
5. ยังไม่ควรเพิ่ม live endpoint จนกว่าจะมีผลทดสอบและ monitoring ที่เพียงพอ
