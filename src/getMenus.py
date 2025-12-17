#!/usr/bin/env python3

import os
import re
import hashlib
from datetime import datetime, timedelta, date, time
from zoneinfo import ZoneInfo

import requests
from dateutil.relativedelta import relativedelta, MO

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ---------------------------
# FIXED IDS (from you)
# ---------------------------
DISTRICT_ID = 400
SCHOOL_ID = "10de21a6-64e7-4bd0-9d8c-8a17d2cfe022"
SERVING_LINE = "Lunch"
MEAL_TYPE = "Lunch"
GRADE = "08"  # 8th grade (your example used 06)
ENABLED_WEEKEND_MENUS = False
PERSON_ID = None  # keep None -> sends PersonId=null

# ---------------------------
# CONFIG
# ---------------------------
TIMEZONE = "America/Chicago"
SERVING_LINE_PREFERRED_REGEX = r"Lunch"

# Google Calendar target (a calendar Skylight syncs)
GOOGLE_CALENDAR_ID = os.environ.get("LUNCH_GCAL_ID", "primary")

GOOGLE_CLIENT_SECRET_FILE = os.environ.get("GOOGLE_CLIENT_SECRET_FILE", "./client_secret.json")
GOOGLE_TOKEN_FILE = os.environ.get("GOOGLE_TOKEN_FILE", "./token.json")

LUNCH_START_LOCAL = time(11, 30)
LUNCH_DURATION_MIN = 30

SCOPES = ["https://www.googleapis.com/auth/calendar"]
BASE = "https://webapis.schoolcafe.com"



# ---------------------------
# SchoolCafé
# ---------------------------
def schoolcafe_get(path: str, params: dict | None = None):
    url = f"{BASE}{path}"
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def week_range_for_today_local(tz: ZoneInfo) -> tuple[date, date]:
    """Current week = Monday..Sunday containing today (script runs Sundays)."""
    today = datetime.now(tz).date()
    monday = today + relativedelta(weekday=MO(-1))
    sunday = monday + timedelta(days=6)
    return monday, sunday

def pick_serving_line(start: date, end: date) -> str:
    data = schoolcafe_get(
        "/api/GetServiceLine",
        params={
            "schoolid": SCHOOL_ID,
            "startdate": start.isoformat(),
            "enddate": end.isoformat(),
            "mealtype": MEAL_TYPE
        },
    )

    candidates: list[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                candidates.append(item)
            elif isinstance(item, dict):
                for k in ("ServingLine", "Text", "Name", "Value"):
                    if k in item and isinstance(item[k], str):
                        candidates.append(item[k])
                        break

    if not candidates:
        raise RuntimeError(f"Could not parse serving lines. Raw response: {data}")

    rx = re.compile(SERVING_LINE_PREFERRED_REGEX, re.IGNORECASE)
    for s in candidates:
        if rx.search(s):
            return s

    return candidates[0]

def fetch_menu_items_week(start: date, end: date, serving_line: str):
    return schoolcafe_get(
        "/api/CalendarView/GetMonthlyMenuitems",
        params={
            "SchoolId": SCHOOL_ID,
            "StartDate": start.isoformat(),
            "EndDate": end.isoformat(),
            "ServingLine": serving_line,
            "MealType": MEAL_TYPE
        }
    )

def normalize_items_by_day(menu_payload) -> dict[date, list[str]]:
    out: dict[date, list[str]] = {}

    def add(d: date, item: str):
        if not item:
            return
        out.setdefault(d, [])
        if item not in out[d]:
            out[d].append(item)

    if isinstance(menu_payload, list):
        for row in menu_payload:
            if not isinstance(row, dict):
                continue

            d_raw = row.get("ServingDate") or row.get("Date") or row.get("ServeDate")
            if not d_raw:
                continue
            d = date.fromisoformat(str(d_raw)[:10])

            desc = row.get("MenuItemDescription") or row.get("ItemName") or row.get("Text")
            if isinstance(desc, str) and desc.strip():
                add(d, desc.strip())

            nested = row.get("MenuItems") or row.get("Items") or row.get("MenuItemList")
            if isinstance(nested, list):
                for it in nested:
                    if isinstance(it, dict):
                        desc2 = it.get("MenuItemDescription") or it.get("ItemName") or it.get("Text")
                        if isinstance(desc2, str) and desc2.strip():
                            add(d, desc2.strip())
                    elif isinstance(it, str) and it.strip():
                        add(d, it.strip())

    return out


# ---------------------------
# Google Calendar
# ---------------------------
def gcal_service():
    creds = None
    if os.path.exists(GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CLIENT_SECRET_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(GOOGLE_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)

def stable_event_id(day: date) -> str:
    raw = f"aisd-smallms-lunch:{SCHOOL_ID}:{day.isoformat()}".encode("utf-8")
    h = hashlib.sha1(raw).hexdigest()
    return f"lunch-{h}"

def upsert_week_events(svc, calendar_id: str, week_items: dict[date, list[str]], tz: ZoneInfo, serving_line: str):
    for d, items in sorted(week_items.items()):
        title = "School Lunch"
        if items:
            first = items[0]
            title = f"School Lunch: {first}" if len(first) <= 60 else "School Lunch"

        start_dt = datetime.combine(d, LUNCH_START_LOCAL, tz)
        end_dt = start_dt + timedelta(minutes=LUNCH_DURATION_MIN)

        description = (
            f"Austin ISD – Small Middle School – {MEAL_TYPE}\n"
            f"Serving line: {serving_line}\n\n"
            + "\n".join(f"• {x}" for x in items)
        )

        event_id = stable_event_id(d)
        body = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE},
            "extendedProperties": {"private": {"source": "schoolcafe", "schoolId": SCHOOL_ID}}
        }

        # Search for existing events on this date to avoid duplicates
        day_start = datetime.combine(d, time(0, 0), tz)
        day_end = datetime.combine(d, time(23, 59, 59), tz)

        existing_events = svc.events().list(
            calendarId=calendar_id,
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            singleEvents=True
        ).execute()

        # Check if an identical event already exists
        identical_event_found = False
        for event in existing_events.get('items', []):
            event_start = event.get('start', {}).get('dateTime', '')
            event_summary = event.get('summary', '')
            event_description = event.get('description', '')

            # Check if this event matches our lunch event exactly
            if (event_start == start_dt.isoformat() and
                event_summary == title and
                event_description == description):
                identical_event_found = True
                print(f"Skipping {d}: identical event already exists (ID: {event.get('id')})")
                break

        if identical_event_found:
            continue

        # Try to update our stable ID event, or create new if it doesn't exist
        try:
            body_with_id = {"id": event_id, **body}
            svc.events().update(calendarId=calendar_id, eventId=event_id, body=body_with_id).execute()
            print(f"Updated event for {d}")
        except Exception:
            svc.events().insert(calendarId=calendar_id, body=body).execute()
            print(f"Created new event for {d}")

def fetch_weekly_menu_by_grade(serving_date: date):
    """
    Calls:
    https://webapis.schoolcafe.com/api/CalendarView/GetWeeklyMenuitemsByGrade
      ?SchoolId=...
      &ServingDate=MM/DD/YYYY
      &ServingLine=Lunch
      &MealType=Lunch
      &Grade=08
      &PersonId=null
      &enabledWeekendMenus=false
    """
    serving_date_str = serving_date.strftime("%m/%d/%Y")  # NOTE: endpoint expects MM/DD/YYYY
    return schoolcafe_get(
        "/api/CalendarView/GetWeeklyMenuitemsByGrade",
        params={
            "SchoolId": SCHOOL_ID,
            "ServingDate": serving_date_str,
            "ServingLine": SERVING_LINE,
            "MealType": MEAL_TYPE,
            "Grade": GRADE,
            "PersonId": "null" if PERSON_ID is None else PERSON_ID,
            "enabledWeekendMenus": str(ENABLED_WEEKEND_MENUS).lower(),
        },
    )

def normalize_weekly_payload(menu_payload) -> dict[date, list[str]]:
    out: dict[date, list[str]] = {}

    def add(d: date, item: str):
        if not item:
            return
        item = item.strip()
        if not item:
            return
        out.setdefault(d, [])
        if item not in out[d]:
            out[d].append(item)

    if not menu_payload:
        return out

    # Case A: list of dict rows with a date and item fields
    if isinstance(menu_payload, list):
        for row in menu_payload:
            if not isinstance(row, dict):
                continue

            d_raw = (
                row.get("ServingDate")
                or row.get("Date")
                or row.get("ServeDate")
                or row.get("MenuDate")
            )
            # Some APIs return MM/DD/YYYY
            d = None
            if isinstance(d_raw, str) and d_raw:
                try:
                    if "/" in d_raw:
                        d = datetime.strptime(d_raw[:10], "%m/%d/%Y").date()
                    else:
                        d = date.fromisoformat(d_raw[:10])
                except Exception:
                    d = None

            # Pull common item name fields
            item = (
                row.get("MenuItemDescription")
                or row.get("ItemName")
                or row.get("Text")
                or row.get("MenuItemName")
            )

            if d and isinstance(item, str):
                add(d, item)

            # Nested items list
            nested = row.get("MenuItems") or row.get("Items") or row.get("MenuItemList")
            if d and isinstance(nested, list):
                for it in nested:
                    if isinstance(it, dict):
                        item2 = it.get("MenuItemDescription") or it.get("ItemName") or it.get("Text")
                        if isinstance(item2, str):
                            add(d, item2)
                    elif isinstance(it, str):
                        add(d, it)

        return out

    # Case B: dict keyed by day/date with arrays
    if isinstance(menu_payload, dict):
        for k, v in menu_payload.items():
            d = None
            if isinstance(k, str):
                try:
                    if "/" in k:
                        d = datetime.strptime(k[:10], "%m/%d/%Y").date()
                    else:
                        d = date.fromisoformat(k[:10])
                except Exception:
                    d = None
            if d and isinstance(v, list):
                for it in v:
                    if isinstance(it, str):
                        add(d, it)
                    elif isinstance(it, dict):
                        item = it.get("MenuItemDescription") or it.get("ItemName") or it.get("Text")
                        if isinstance(item, str):
                            add(d, item)
        return out

    return out

def iter_days_from_payload(payload: dict):
    """
    SchoolCafe sometimes returns:
      A) {"12/15/2025": {...}, "12/16/2025": {...}}
    instead of:
      B) {"Days": [{"ServingDate": "...", ...}, ...]}

    This yields (day_date, day_obj) for the dict-keyed shape.
    """
    if not isinstance(payload, dict):
        return

    # Shape A: top-level keys are dates like "12/15/2025"
    # (what your Raw payload shows)
    for k, v in payload.items():
        if not isinstance(k, str):
            continue
        try:
            d = datetime.strptime(k, "%m/%d/%Y").date()
        except ValueError:
            # ignore non-date keys if they exist
            continue
        if isinstance(v, dict):
            yield d, v


def main():
    tz = ZoneInfo(TIMEZONE)
    week_start, week_end = week_range_for_today_local(tz)

    # The API wants a single ServingDate; use the Monday of the current week
    payload = fetch_weekly_menu_by_grade(week_start)

    week_end   = week_start + timedelta(days=6)

    days = list(iter_days_from_payload(payload))

    # 👇 PUT THE week_items BLOCK RIGHT HERE
    week_items = []
    for d, day_obj in days:
        if not (week_start <= d <= week_end):
            continue

        for category, items in (day_obj or {}).items():
            if not isinstance(items, list):
                continue

            for item in items:
                if isinstance(item, dict) and item.get("MenuItemId") == 0:
                    continue
                if isinstance(item, dict) and (item.get("MenuItemDescription") or "").strip() == "A menu has not been published for this day.":
                    continue

                week_items.append({
                    "date": d.isoformat(),
                    "category": category,
                    "description": item.get("MenuItemDescription"),
                    "menu_item_id": item.get("MenuItemId"),
                })

    from collections import defaultdict
    items_by_day = defaultdict(list)

    for it in week_items:
        # it["date"] is "YYYY-MM-DD"
        d = date.fromisoformat(it["date"])
        desc = it.get("description", "")
        if desc and desc not in items_by_day[d]:
            items_by_day[d].append(desc)

    items_by_day = dict(items_by_day)

    if not week_items:
        raise RuntimeError(f"No menu items found for week starting {week_start}. Raw payload: {payload}")

    svc = gcal_service()
    upsert_week_events(svc, GOOGLE_CALENDAR_ID, items_by_day, tz, SERVING_LINE)

    print(f"✅ Imported lunch menu for {len(items_by_day)} day(s). Week: {week_start}..{week_end}")


if __name__ == "__main__":
    main()
