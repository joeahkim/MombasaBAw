### Requirements

- Python 3.8 or higher
- Google Chrome browser
- Internet connection

---

### Installation & Setup

#### 1. Clone the repository

```bash
git clone https://github.com/joeahkim/MombasaBAw.git
cd MombasaBAw
```

### 2. Create a virtual environment

#### Windows

```
python -m venv venv
venv\Scripts\activate
```

#### macOS / Linux

```
python3 -m venv venv
source venv/bin/activate
```

You’ll see (venv) in your terminal when it’s active.

### 3. Make chromedriver executable

##### (Linux and macOs)

```
chmod +x chromedriver
```

#### Windows

```
  pip install selenium webdriver-manager
```

### 4. Run the bot

```
python test.py
```

You’ll see output like:

```
Mombasa Awards Auto-Voter STARTED – runs all day (Ctrl+C to stop)

  STARTING CYCLE #1 @ 2025-11-24 14:30:22

[14:30:25] Voting BEST START UP BUSINESS → Intrasoft Technologies Limited
Successfully voted BEST START UP BUSINESS!
...
All 7 votes completed in cycle #1!
Taking long break ≈ 124 minutes ...
Press Ctrl + C at any time to stop the bot gracefully.
```
