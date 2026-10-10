# Personal file system demo corpus

Try it: index this folder from the Streamlit sidebar (set the folder path to `examples/`), or run `PMA_FILES_DIR=examples python scripts/index_files.py`. Then search for e.g. `holiday plan`, `exercise plan` or `statement of charges`.

```

Purpose
-------
Synthetic corpus for evaluating semantic file search, synonym matching, file parsing, metadata filtering and numeric-noise resistance. Every name, address, institution, company, identifier, email domain and payment reference is fictional. Nothing here is an authentic bill, ticket, offer or booking.

Folders
-------
college/   OS, DBMS, ML notes; assignment brief; exam timetable; raw numeric lab measurements; ML and OS supporting notes.
finance/   Two electricity statements, rent receipt, freelance invoice, monthly budget, numeric expense export.
travel/    Goa itinerary, rail confirmation, hotel-booking email, general packing notes, short Goa PPTX.
personal/  Hostel counselling notice, gym plan, recipe, journal entry, grocery list.
work/      Internship offer, sync notes, report draft, weekly update, semantic-search PPTX.

Search-test concepts
--------------------
- bill / invoice / statement / dues / charges
- rent receipt / proof of accommodation payment
- trip / journey / itinerary / holiday plan / train booking
- counselling / wellbeing / hostel support
- workout / gym routine / exercise plan
- client payment request / freelance invoice
- semantic search / similar meaning / query paraphrase
- numeric dump as a noise candidate, except when the query explicitly asks for expenses or measurements

Formats
-------
TXT, DOCX and 3 short PPTX files. Some documents include tables. Most narrative documents target 150-600 words; the raw numeric dump is intentionally table-dominant.

Reminder
--------
This is a generated test fixture, not a set of real personal records. Do not treat synthetic references as working account, ticket or payment identifiers.
```
