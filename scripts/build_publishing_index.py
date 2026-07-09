from __future__ import annotations

import json
from pathlib import Path

import yaml


WEBSITE = Path("sagp_website")
OUTPUT = WEBSITE / "public/platform/publishing_index.json"


def normalize_date(value):
    return "" if value is None else str(value)[:10]


def clean(value):
    return "" if value is None else str(value)


def load_events():
    events = []

    for path in sorted((WEBSITE / "content/events").glob("*/*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        event = data["event"]
        event_type = path.parent.name
        year = path.stem
        dates = event.get("dates", {})
        location = event.get("location", {})
        attendance = event.get("attendance", {})
        hero = event.get("hero", {})

        events.append({
            "kind": "event",
            "id": f"{event_type}/{year}",
            "event_id": event.get("id", ""),
            "type": event_type,
            "year": year,
            "title": event.get("title", f"{event_type} {year}"),
            "subtitle": event.get("subtitle", ""),
            "status": event.get("status", ""),
            "description": event.get("description", ""),
            "date": normalize_date(dates.get("start")),
            "dates": {
                "start": normalize_date(dates.get("start")),
                "end": normalize_date(dates.get("end")),
                "timezone": clean(dates.get("timezone")),
                "timezone_iana": clean(dates.get("timezone_iana")),
            },
            "location": {
                "mode": clean(location.get("mode")),
                "venue": clean(location.get("venue")),
                "city": clean(location.get("city")),
                "region": clean(location.get("region")),
                "country": clean(location.get("country")),
                "url": clean(location.get("url")),
            },
            "attendance": {
                "instructions": clean(attendance.get("instructions")),
                "contact_email": clean(attendance.get("contact_email")),
            },
            "hero": {
                "kicker": clean(hero.get("kicker")),
                "title": clean(hero.get("title")),
                "subtitle": clean(hero.get("subtitle")),
                "image": clean(hero.get("image")),
            },
            "detail": event.get("description") or hero.get("subtitle", ""),
            "source_yaml": str(path.relative_to(WEBSITE)),
        })

    return sorted(events, key=lambda x: x["date"], reverse=True)


def load_calls():
    calls = []

    for path in sorted((WEBSITE / "content/calls").glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        call = data["call"]

        deadline = ""
        if call.get("deadlines"):
            deadline = normalize_date(call["deadlines"][0].get("date"))

        calls.append({
            "kind": "call",
            "id": path.stem,
            "title": call.get("hero", {}).get("title") or call.get("title") or path.stem,
            "status": call.get("status", ""),
            "deadline": deadline,
            "detail": call.get("summary", ""),
            "source_yaml": str(path.relative_to(WEBSITE)),
        })

    return sorted(calls, key=lambda x: x["deadline"])


def main():
    payload = {
        "events": load_events(),
        "calls": load_calls(),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(OUTPUT)
    print(f"{len(payload['events'])} events")
    print(f"{len(payload['calls'])} calls")


if __name__ == "__main__":
    main()
