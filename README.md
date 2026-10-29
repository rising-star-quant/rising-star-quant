# 🌟 Rising Star Trend Engine (מנוע גילוי מניות מומנטום)

מערכת מיקרו-מודולרית מבוססת פייתון לגילוי, סינון, דירוג וניהול סיכונים עבור מניות מומנטום פורצות (Rising Stars), כוללת סריקה אוטומטית בענן עם GitHub Actions והתראות טלגרם בזמן אמת.

---

## 📁 מבנה הפרויקט (Project Architecture)

```text
rising-star-engine/
├── .github/
│   └── workflows/
│       └── run_engine.yml        # קובץ ההפעלה האוטומטי בענן (GitHub Actions)
├── core/                         # תיקיית המיקרו-מודולים
│   ├── __init__.py
│   ├── dataconnector.py          # מודול השאיבה (yfinance / exponential backoff)
│   ├── ruleengine.py             # מודול תנאי הסף של S&P (רווחיות, שווי, נזילות)
│   ├── indicatorengine.py        # מודול חישובים טכניים (MA50, נפחים, 20d High, ATR)
│   ├── scoringengine.py          # מודול שקלול הציון (0-100)
│   ├── riskguard.py              # מודול ניהול סיכונים, סטופ לוס דינמי ויעדי רווח
│   └── notificationhub.py        # מודול שליחת התראות לטלגרם
├── tests/                        # תיקיית בדיקות יחידה
│   └── test_modules.py
├── watchlist.csv                 # רשימת המניות לסריקה
├── main.py                       # הקובץ הראשי שמחבר את הכל ומריץ
├── requirements.txt              # רביזיות וספריות נדרשות (pandas, yfinance, requests...)
└── README.md
```

---

## 🧩 המיקרו-מודולים של המערכת

1. **`core/dataconnector.py`**:
   שואב היסטוריית מחירים יומית (OHLCV) ונתונים פונדמנטליים באמצעות `yfinance` עם לוגיקת Exponential Backoff ו-Jitter להתמודדות עם מגבלות קריאה (HTTP 429).

2. **`core/ruleengine.py`**:
   מסנן תנאי סף מוסדיים בסגנון מדד S&P:
   - שווי שוק מינימלי (מעל 1 מיליארד דולר לחברות צמיחה).
   - רווחיות חיובית מצטברת ב-12 החודשים האחרונים (Positive TTM Net Income).
   - נזילות מספקת (מחזור דולרי יומי מעל 5 מיליון דולר).
   - סינון מניות פני (מחיר מעל 5 דולר).

3. **`core/indicatorengine.py`**:
   מחשב ממוצעים נעים (MA20, MA50, MA200), בדיקת פריצת שיא 20 ימים (20d High Breakout), בדיקת התרחבות מחזורים (Volume Surge) ומדד תנודתיות ATR14.

4. **`core/scoringengine.py`**:
   אלגוריתם שקלול מבוסס 100 נקודות המדרג כל מניה לקטגוריות:
   - **`STRONG_RISING_STAR` (80-100)**: מובילת מומנטום מובהקת בפריצה עם ווליום חריג.
   - **`EMERGING_CANDIDATE` (65-79)**: מניה מתקרבת לפריצה באיכות גבוהה.
   - **`WATCHLIST` (50-64)**: מניה בגיבוש הדורשת מעקב.
   - **`AVOID` (< 50)**: אינה עומדת בקריטריונים.

5. **`core/riskguard.py`**:
   תוכנית מסחר וניהול סיכונים א-סימטרית:
   - חישוב סטופ לוס דינמי המבוסס על ATR ומבנה ה-MA50 (מקסימום סיכון 7.5%).
   - חישוב יעדי רווח מדורגים: Target 1 (2R), Target 2 (3R), Target 3 (5R).
   - חישוב גודל פוזיציה מומלץ (כמות מניות לפי תקציב סיכון מוגדר, ברירת מחדל $1,000).

6. **`core/notificationhub.py`**:
   מפיץ הודעות מעוצבות לטלגרם הכוללות את כרטיס המניה, הציון, הסטופ לוס ויעדי הרווח.

---

## ⚡ הוראות התקנה והרצה מקומית

### 1. התקנת סביבת עבודה ותלויות:
```bash
git clone https://github.com/<YOUR_USER>/rising-star-engine.git
cd rising-star-engine

# יצירת סביבה וירטואלית
python3 -m venv venv
source venv/bin/activate  # בווינדוס: venv\Scripts\activate

# התקנת הספריות
pip install -r requirements.txt
```

### 2. הרצת בדיקות יחידה (Unit Tests):
```bash
pytest tests/ -v
```

### 3. הרצת המנוע:
```bash
# הרצה רגילה עם רשימת ברירת המחדל
python main.py

# הרצה עם קובץ Watchlist מותאם אישית
python main.py --watchlist watchlist.csv --min-score 75

# הרצה ללא שליחת טלגרם (Dry Run)
python main.py --no-telegram
```

---

## 🤖 הפעלה אוטומטית בענן (GitHub Actions)

הקובץ `.github/workflows/run_engine.yml` מוגדר להריץ את המנוע באופן אוטומטי בימי שני עד שישי בשעה 21:30 UTC (לאחר סגירת המסחר בוול-סטריט).

### הגדרת Secrets ב-GitHub עבור טלגרם:
1. פתח את המאגר שלך ב-GitHub ועבור ל:
   **Settings > Secrets and variables > Actions > New repository secret**
2. הוסף שני ערכים:
   - `TELEGRAM_BOT_TOKEN`: הטוקן שקיבלת מ-BotFather בטלגרם.
   - `TELEGRAM_CHAT_ID`: ה-ID של הערוץ או הצ'אט הפרטי שלך.
