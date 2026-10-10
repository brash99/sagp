BEGIN IMMEDIATE;

UPDATE members
SET region = 'Canada',
    notes = trim(coalesce(notes || char(10), '') || 'Region label normalized 2026-10-10 from Canada Ontario to Canada.'),
    updated_at = datetime('now')
WHERE person_id = 'SAGP001178' AND region = 'Canada Ontario';

UPDATE members
SET region = 'Canada',
    notes = trim(coalesce(notes || char(10), '') || 'Region label normalized 2026-10-10 from Canada Montréal to Canada.'),
    updated_at = datetime('now')
WHERE person_id = 'SAGP001132' AND region = 'Canada Montréal';

UPDATE members
SET region = 'Europe',
    notes = trim(coalesce(notes || char(10), '') || 'Region label normalized 2026-10-10 from Greece to Europe.'),
    updated_at = datetime('now')
WHERE person_id = 'SAGP001823' AND region = 'Greece';

UPDATE members
SET region = 'USA Eastern',
    notes = trim(coalesce(notes || char(10), '') || 'Region label normalized 2026-10-10 from Eastern to USA Eastern.'),
    updated_at = datetime('now')
WHERE person_id = 'SAGP001820' AND region = 'Eastern';

UPDATE members
SET region = 'USA Central',
    notes = trim(coalesce(notes || char(10), '') || 'Region label normalized 2026-10-10 from US Central to USA Central.'),
    updated_at = datetime('now')
WHERE person_id = 'SAGP000642' AND region = 'US Central';

UPDATE members
SET region = 'East and Southeast Asia',
    notes = trim(coalesce(notes || char(10), '') || 'Region label normalized 2026-10-10 from Taiwan to East and Southeast Asia.'),
    updated_at = datetime('now')
WHERE person_id = 'SAGP000991' AND region = 'Taiwan';

COMMIT;
