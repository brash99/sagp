You are converting a finalized SAGP event document into canonical SAGP event YAML.

Return YAML only. Do not include markdown fences, commentary, explanations, or notes.

Use this exact top-level structure:

event:
  id:
  title:
  subtitle:
  type:
  status:
  description:
  attendance:
    instructions:
    contact_email:
  dates:
    start:
    end:
    timezone:
    timezone_iana:
  location:
    mode:
    venue:
    city:
    region:
    country:
    url:
  hero:
    kicker:
    title:
    subtitle:
    image:
  sessions:

Rules:
- Do not invent facts.
- Leave unknown fields blank.
- Preserve speaker names, affiliations, titles, and abstracts as accurately as possible.
- Use status: draft.
- Use the supplied event type and year.
- Use /assets/images/parthenon_night.jpg as the default hero image.
- For annual conferences, create sessions when session titles, times, moderators, and presentations are evident.
- For distinguished lectureships, create one Distinguished Lecture session when possible.
- YAML must be valid.
- Dates should use YYYY-MM-DD when known.
- Times should use HH:MM 24-hour format when known.

- For annual conferences, session times often appear immediately before a session title or moderator line. Attach that time to the following session as start_time.
- Do not omit session start_time if a nearby time such as 7:00am PST or 11:00am PST is present.
