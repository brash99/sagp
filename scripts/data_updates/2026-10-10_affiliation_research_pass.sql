BEGIN IMMEDIATE;

UPDATE members SET institution = 'Idaho State University', region = 'USA Mountain',
  notes = trim(coalesce(notes || char(10), '') || 'Affiliation verified 2026-10-10: Associate Professor of Philosophy, Idaho State University. Source: https://www.isu.edu/philosophy/about/faculty/staffdirectoryentries/name-244510-en.html'),
  updated_at = datetime('now') WHERE person_id = 'SAGP000980';

UPDATE members SET institution = 'University of Oxford', region = 'Europe',
  notes = trim(coalesce(notes || char(10), '') || 'Affiliation verified 2026-10-10: Associate Professor and Tutorial Fellow in Ancient Philosophy, University of Oxford. Source: https://www.philosophy.ox.ac.uk/people/marion-durand'),
  updated_at = datetime('now') WHERE person_id = 'SAGP001144';

UPDATE members SET institution = 'Loyola University Chicago', region = 'USA Central',
  notes = trim(coalesce(notes || char(10), '') || 'Affiliation verified 2026-10-10: PhD student in Philosophy, Loyola University Chicago. Source: https://www.luc.edu/philosophy/currentgraduatestudents/'),
  updated_at = datetime('now') WHERE person_id = 'SAGP001244';

UPDATE members SET institution = 'National and Kapodistrian University of Athens', region = 'Europe',
  notes = trim(coalesce(notes || char(10), '') || 'Affiliation verified 2026-10-10: Professor for the History of Philosophy, National and Kapodistrian University of Athens. Source: https://en.phs.uoa.gr/staff/panagiotis_thanassas/'),
  updated_at = datetime('now') WHERE person_id = 'SAGP000571';

UPDATE members SET institution = 'Skidmore College', region = 'USA Eastern',
  notes = trim(coalesce(notes || char(10), '') || 'Affiliation verified 2026-10-10: Associate Professor of Philosophy, Skidmore College. Source: https://www.skidmore.edu/_dev/philosophy/faculty/silvia-carli.php'),
  updated_at = datetime('now') WHERE person_id = 'SAGP000200';

UPDATE members SET institution = 'University of Liège', region = 'Europe',
  notes = trim(coalesce(notes || char(10), '') || 'Affiliation verified 2026-10-10: Lecturer in the Department of Philosophy, University of Liège. Source: https://www.facphl.uliege.be/cms/c_11248080/fr/comment-devenir-un-philosophe-grec'),
  updated_at = datetime('now') WHERE person_id = 'SAGP001543';

UPDATE members SET institution = 'Oklahoma State University', region = 'USA Central',
  notes = trim(coalesce(notes || char(10), '') || 'Last verified academic affiliation 2026-10-10: Visiting Assistant Professor, Oklahoma State University. Source: https://philos.humanities.mcmaster.ca/our-community/current-and-former-graduate-students/'),
  updated_at = datetime('now') WHERE person_id = 'SAGP001197';

UPDATE members SET institution = 'Alaska Pacific University', region = 'USA Western',
  notes = trim(coalesce(notes || char(10), '') || 'Affiliation corroborated 2026-10-10: Philosophy, Alaska Pacific University. Source: https://historyofphilosophyroundtable.sites.luc.edu/'),
  updated_at = datetime('now') WHERE person_id = 'SAGP000519';

UPDATE members SET institution = 'UCLouvain', region = 'Europe',
  notes = trim(coalesce(notes || char(10), '') || 'Recent affiliation verified 2026-10-10: Research Fellow, UCLouvain. Source: https://rbphilosophy.com/assets/papers/book-of-abstracts-international-aristotelian-conference-2025.pdf'),
  updated_at = datetime('now') WHERE person_id = 'SAGP001461';

UPDATE members SET institution = 'University of North Carolina at Chapel Hill', region = 'USA Eastern',
  notes = trim(coalesce(notes || char(10), '') || 'Historical/emeritus affiliation verified 2026-10-10: retired from full-time teaching at the University of North Carolina at Chapel Hill. Source: https://www.sas.rochester.edu/phl/assets/pdf/2019newsletterecopy.pdf'),
  updated_at = datetime('now') WHERE person_id = 'SAGP000439';

UPDATE members SET institution = 'University of Southern California', region = 'USA Western',
  notes = trim(coalesce(notes || char(10), '') || 'Last verified institutional affiliation 2026-10-10: USC Gould School of Law; earlier ancient-philosophy work at Indiana University Bloomington. Source: https://usc.academia.edu/JonathanHecht'),
  updated_at = datetime('now') WHERE person_id = 'SAGP001050';

UPDATE members SET institution = 'Prairie College', region = 'Canada',
  notes = trim(coalesce(notes || char(10), '') || 'Last verified academic affiliation 2026-10-10: Prairie College, Alberta; later public evidence indicates work outside academia. Source: https://jcrt.org/archives/06.3/lorentzen.pdf'),
  updated_at = datetime('now') WHERE person_id = 'SAGP001181';

UPDATE members SET institution = 'University of Bonn', region = 'Europe',
  notes = trim(coalesce(notes || char(10), '') || 'Most recent academic affiliation located 2026-10-10: Rheinische Friedrich-Wilhelms-Universität Bonn; treat as last verified, not confirmed current. Source: https://ojs.library.dal.ca/dionysius/article/download/9910/8745'),
  updated_at = datetime('now') WHERE person_id = 'SAGP000699';

UPDATE members SET institution = 'Biola University', region = 'USA Western', active = 0,
  membership_status = 'Deceased',
  notes = trim(coalesce(notes || char(10), '') || 'Deceased August 2023. Historical affiliation: Professor, Torrey Honors College, Biola University. Verified 2026-10-10. Source: https://www.biola.edu/blogs/biola-news/2023/biola-grieves-passing-of-professor-alina-beary'),
  updated_at = datetime('now') WHERE person_id = 'SAGP000872';

COMMIT;
