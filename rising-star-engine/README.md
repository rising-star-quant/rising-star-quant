# 🌟 Rising Star Trend Engine (מנוע גילוי מניות מומנטום וסריקה כמותית)

מערכת מיקרו-מודולרית מבוססת פייתון (Strictly Headless Backend) לגילוי, סינון, דירוג, ניהול סיכונים, בקטסטינג היסטורי וסחר מדומה (Paper Trading) עבור מניות מומנטום פורצות (Rising Stars), כוללת סריקה אוטומטית בענן עם GitHub Actions, דשבורד ניטור אינטראקטיבי, והתראות טלגרם בזמן אמת.

---

## 📁 מבנה הפרויקט (Project Architecture)

```text
rising-star-engine/
├── .github/
│   └── workflows/
│       ├── quant_scan.yml        # קובץ ההפעלה האוטומטי בענן (21:30 UTC אחרי סגירת וול סטריט)
│       └── run_engine.yml        # תאימות לאחור
├── core/                         # תיקיית המיקרו-מודולים (Headless Core)
│   ├── __init__.py
│   ├── dataconnector.py          # מודול השאיבה (yfinance / exponential backoff & jitter)
│   ├── ruleengine.py             # מודול תנאי הסף של S&P (100% חוקי כשירות פורמליים)
│   ├── indicatorengine.py        # מודול חישובים טכניים (250 נרות, שיפוע MA50, ווליום, פריצות)
│   ├── scoringengine.py          # מודול שקלול הציון (40/30/20/10 + Backtest Gatekeeper)
│   ├── riskguard.py              # מודול ניהול סיכונים, ATR סטופ לוס דינמי ויעדי רווח 1R/2R/3R/5R
│   ├── universe.py               # מודול שליפת S&P 500, שמירה במטמון וסריקה באצוות
│   ├── notificationhub.py        # מודול שליחת התראות וסיכומים לטלגרם
│   ├── backtester.py             # מנוע בקטסטינג היסטורי (Sharpe, Drawdown, Win Rate, Profit Factor)
│   └── portfoliotracker.py       # מודול מעקב תיק וירטואלי (Paper Trading) ובדיקות סיכון אוטומטיות
├── scripts/
│   └── run_nightly_scan.sh       # סקריפט הרצה עצמאי לשרתים / קרון מקומי
├── tests/                        # תיקיית בדיקות יחידה מלאה (Pytest)
│   ├── test_engines.py
│   ├── test_scoring_risk.py
│   ├── test_sprint4.py
│   └── test_sprint5.py
├── backtest.py                   # קובץ CLI עצמאי להרצת בקטסט על מניות נבחרות או S&P 500
├── main.py                       # הקובץ הראשי שמחבר את הכל ומריץ סריקה ומעקב תיק
├── portfolio.json                # קובץ סטטוס התיק הווירטואלי (פוזיציות פתוחות, נעולות ויתרות)
├── scan_results.json             # תוצאות הסריקה העדכניות בפורמט JSON
├── scan_results.csv              # תוצאות הסריקה בפורמט טבלאי
├── watchlist.csv                 # רשימת המניות לסריקה
├── requirements.txt              # תלויות פייתון (pandas, yfinance, pydantic, numpy, requests...)
└── README.md
```

---

## 🧩 המיקרו-מודולים של המערכת (Core Engines)

1. **`core/dataconnector.py`**:
   שואב היסטוריית מחירים יומית (OHLCV) ונתונים פונדמנטליים עם לוגיקת Exponential Backoff ו-Jitter להתמודדות איתנה עם הגבלות קצב (HTTP 429).

2. **`core/ruleengine.py`**:
   מסנן 100% מתנאי הסף הפורמליים של מדד S&P 500:
   - התאגדות בארה"ב ורישום בבורסות המובילות (NYSE, NASDAQ, Cboe עם מיפוי אוטומטי של קודי Yahoo כמו NMS/NGM/NCM).
   - שווי שוק מינימלי ($18.0B ומעלה).
   - יחס נזילות מתואם צף > 1.0 ושיעור מניות צפות מעל 50%.
   - רווחיות GAAP חיובית ב-4 הרבעונים האחרונים וברבעון האחרון.

3. **`core/indicatorengine.py`**:
   מנתח 250 נרות יומיים תוך שימוש בלעדי באינדוקס `.iloc[]` (ללא FutureWarnings):
   - חישוב MA50, MA200 ושיפוע חיובי ב-20 ימים.
   - יחס מחזורים בימי עליות מול ירידות (איסוף מוסדי מעל 1.30x).
   - זיהוי פריצות של שיא 20 ימים ושיא 52 שבועות.
   - חישוב תנודתיות 14d ATR.

4. **`core/scoringengine.py`**:
   שקלול מולטי-פקטור נורמלי (0-100):
   - מגמה טכנית (40%), ווליום מוסדי (30%), סנטימנט סקטוריאלי (20%), שורט אינטרסט (10%).
   - התראת קנייה (BUY ALERT) בציון 85 ומעלה יחד עם פריצה מאומתת.
   - שומר סף (Backtest Gatekeeper): Profit Factor $\ge$ 1.20 ו-Win Rate $\ge$ 50%.

5. **`core/riskguard.py`**:
   ניהול סיכונים מתקדם:
   - סטופ-לוס דינמי מבוסס ATR(14) כפול 2.0 או Trailing Stop של 10% מהשיא.
   - יעדי רווח אסימטריים: 1R, 2R, 3R, 5R.
   - חישוב גודל פוזיציה כמותי לפי תקציב סיכון מוגדר (למשל 1% מתיק של $100,000).

6. **`core/backtester.py`**:
   מנוע סימולציה היסטורית רב-שנתית:
   - הרצה בחלונות נע של 250 ימים.
   - חישוב מדדי ביצועים: תשואה שנתית, מדד שארפ שנתי (Sharpe Ratio), Drawdown מקסימלי, Win Rate, ו-Profit Factor.
   - יומן עסקאות מלא וקו עקומת הון (Equity Curve).

7. **`core/portfoliotracker.py`**:
   ספר פקודות ומעקב אחר תיק וירטואלי (Paper Trading):
   - פתיחת פוזיציות אוטומטית בהתראות קנייה (Buy Alerts).
   - בדיקת סיכונים שוטפת (RiskGuard Audit) נגד פריצת סטופ-לוס נגרר או שבירת ממוצע 50.
   - שמירה וטעינה מובנית מקובץ `portfolio.json`.

8. **`core/universe.py` & `core/notificationhub.py`**:
   - שאיבת כל 503 מניות S&P 500 מוויקיפדיה עם מטמון מקומי ל-7 ימים.
   - שליחת כרטיסי התראות מעוצבים ודוח סיכום יומי לטלגרם.

---

## 🚀 הוראות הרצה (CLI Execution)

### הרצת סריקת שוק מלאה (S&P 500)
```bash
python main.py --sp500 --equity 100000 --risk-pct 1.0 --batch-size 25
```

### הרצת סריקה על Watchlist מותאם אישית
```bash
python main.py --watchlist watchlist.csv --equity 100000 --risk-pct 1.0
```

### הרצת בקטסטינג היסטורי
```bash
python backtest.py --tickers NVDA CRWD PLTR AAPL MSFT --capital 100000 --trailing-stop 0.10
```

### הרצת בדיקות יחידה
```bash
pytest tests/ -v
```

### הרצה אוטומטית באמצעות סקריפט לינוקס
```bash
./scripts/run_nightly_scan.sh --sp500
```
