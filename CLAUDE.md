# CLAUDE.md - Football Coaches Database System

## Agent Instructions

This file contains instructions for building an automated football coaches database that scrapes and compiles comprehensive profiles from Transfermarkt for projectFIVE.

You operate within a 3-layer architecture that separates concerns to maximize reliability. LLMs are probabilistic, whereas most business logic is deterministic and requires consistency. This system fixes that mismatch.

---

## The 3-Layer Architecture

### **Layer 1: Directive (What to do)**

- Basically just SOPs written in Markdown, live in `directives/`
- Define the goals, inputs, tools/scripts to use, outputs, and edge cases
- Natural language instructions, like you'd give a mid-level employee

### **Layer 2: Orchestration (Decision making)**

- This is you. Your job: intelligent routing.
- Read directives, call execution tools in the right order, handle errors, ask for clarification, update directives with learnings
- You're the glue between intent and execution. E.g., you don't try scraping websites yourself—you read `directives/build_full_profile.md` and come up with inputs/outputs and then run `execution/scrape_transfermarkt.py`

### **Layer 3: Execution (Doing the work)**

- Deterministic Python scripts in `execution/`
- Environment variables, api tokens, etc are stored in `.env`
- Handle web scraping, data processing, database operations, Google Sheets updates
- Reliable, testable, fast. Use scripts instead of manual work. Commented well.

**Why this works:** If you do everything yourself, errors compound. 90% accuracy per step = 59% success over 5 steps. The solution is push complexity into deterministic code. That way you just focus on decision-making.

---

## Operating Principles

### **1. Check for tools first**

Before writing a script, check `execution/` per your directive. Only create new scripts if none exist.

### **2. Self-anneal when things break**

- Read error message and stack trace
- Fix the script and test it again (unless it uses paid tokens/credits/etc—in which case you check w user first)
- Update the directive with what you learned (rate limits, timing, edge cases, HTML structure changes)
- Example: Transfermarkt blocks your IP → you research → find they require headers/delays → rewrite script to add user agents and rate limiting → test → update directive

### **3. Update directives as you learn**

Directives are living documents. When you discover:
- Transfermarkt HTML structure changes
- Better CSS selectors or XPath queries
- Common parsing errors or missing data patterns
- Optimal scraping delays to avoid blocks

...update the directive. But don't create or overwrite directives without asking unless explicitly told to. Directives are your instruction set and must be preserved (and improved upon over time, not extemporaneously used and then discarded).

### **4. Respect website policies**

- Always implement reasonable delays between requests (2-5 seconds minimum)
- Use proper User-Agent headers
- Cache results to avoid repeat scraping
- Never overwhelm the server with parallel requests

---

## Self-annealing Loop

Errors are learning opportunities. When something breaks:

1. **Fix it** - Debug the scraping logic, update selectors, handle edge cases
2. **Update the tool** - Modify the Python script with improved error handling
3. **Test tool** - Run against multiple coaches to ensure it works reliably
4. **Update directive** - Document the new flow, edge cases, and lessons learned
5. **System is now stronger** - Next time this scenario occurs, it's handled automatically

---

## File Organization

### **Directory structure:**

```
/tmp/                           # All intermediate files (never commit)
  ├── cache/                    # Cached Transfermarkt responses
  └── raw_html/                 # Raw HTML for debugging

execution/                      # Python scripts (the deterministic tools)
  ├── scrape_transfermarkt.py   # Main scraper for coach profiles
  ├── scrape_teammates.py       # Get player career teammates
  ├── scrape_players_used.py    # Get players coached statistics
  └── export_to_sheets.py       # Upload results to Google Sheets

directives/                     # SOPs in Markdown (the instruction set)
  ├── scrape_coach_profile.md   # How to get basic coach info
  ├── scrape_teammates.md       # How to get playing career connections
  └── build_full_profile.md     # Orchestration: combine all data sources

data/                           # Persistent data
  └── coaches_cache.json        # Local cache of scraped coaches

.env                            # Environment variables and API keys
credentials.json                # Google Sheets OAuth credentials
token.json                      # Google Sheets auth token
```

---

## Output Structure (Google Sheets)

Each row = one coach with columns:

| Column | Data | Source |
|--------|------|--------|
| A | Coach Name | Profile |
| B | Nationality | Profile |
| C | Age / DOB | Profile |
| D | Current Role | Profile |
| E | Current Club | Profile |
| F | License Level | Profile |
| G | Agent Name | Profile |
| H | Agent Agency | Profile |
| I | TM Profile Link | Input |
| J | Career History | Profile (formatted) |
| K | Key Teammates (Players) | Teammates page |
| L | Coaches Worked With | Career history + teammates |
| M | Sporting Directors Worked With | Career history + teammates |
| N | Top Players Coached | Players Used (filtered: 20+ games, 70+ min avg) |
| O | Background Info Summary | AI-generated from all sources |

---

## Summary

You sit between human intent (directives) and deterministic execution (Python scripts). Read instructions, make decisions, call tools, handle errors, continuously improve the system.

Be pragmatic. Be reliable. Self-anneal.
