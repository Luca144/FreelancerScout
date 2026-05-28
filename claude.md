# Freelancer Scout

Stündlicher Crawler für freelancermap.de, der relevante Projekte filtert und auf einer statischen Webseite (GitHub Pages) anzeigt. Mobile-first, mit Browser-Notification und Sound bei neuen Treffern.

---

## Arbeitsweise für Claude Code

**Wichtig: Arbeite eigenständig. Frag NUR nach, wenn:**

1. Eine Phase abgeschlossen ist und ein Smoke Test durch den Menschen ansteht (siehe Definition of Done je Phase).
2. Eine echte Architektur-Entscheidung ansteht, die nicht in dieser Spec geklärt ist.
3. Eine externe Quelle (z.B. RSS-Feed-Struktur) sich anders verhält als erwartet und das Auswirkungen auf das Datenmodell hat.

**Nicht nachfragen für:**

- Refactorings innerhalb einer Phase
- Variablennamen, Dateinamen, interne Struktur
- Tests hinzufügen (immer machen)
- Linter-Warnungen beheben (immer machen)
- Edge Cases im Code-Bereich (selbst entscheiden, dokumentieren in Docstring)

**Ablauf pro Phase:**

1. Phase implementieren.
2. Tests schreiben und grün bekommen.
3. Linter (`ruff check .`) und Formatter (`ruff format .`) grün bekommen.
4. Kurzer Statusbericht: Was wurde gebaut, wie testet der Mensch, welche Files wurden angefasst.
5. **STOP**. Auf Bestätigung warten, bevor die nächste Phase startet.

---

## Architektur (gilt für alle Phasen)

### Stack

- Python 3.11+
- `requests` (HTTP)
- `jinja2` (HTML-Template)
- `pytest` + `pytest-mock` (Tests)
- `ruff` (Lint + Format)
- Vanilla JS im Frontend, kein Framework
- GitHub Actions als Scheduler
- GitHub Pages als Hosting

Keine weiteren Dependencies ohne Rückfrage.

### Datenquelle

Projekt-Listing direkt von freelancermap.de:

```
https://www.freelancermap.de/projekte
```

Die ursprünglich vorgesehene RSS-Quelle (freelance-o-mat) ist seit 2026-05-27 nachweislich abgeschaltet (rss-feeds.html liefert 410 Gone, Feed-Endpoints 404). freelancermap.de selbst veröffentlicht keinen öffentlichen RSS-Feed.

**Format:** Die Projekt-Übersichtsseite ist eine React-Anwendung. Im HTML-Body steht ein `<script type="application/json">`-Tag mit dem vollständigen initialen State. Pfade in diesem JSON-Blob:

- `initialResults` — reguläre Projekte (~22 Items, erste Seite)
- `initialTopResults` — gesponserte Top-Projekte (~10 Items)

Pro Projekt mindestens diese Felder: `id`, `slug`, `title`, `description` (HTML im `ql-editor`-Wrapper), `created` (ISO), `updated` (ISO), `plink` (relativer URL-Slug zur Detailseite).

Mapping ins Datenmodell:
- `id` (Projekt) = SHA-256(full_url)[:16] — der freelancermap-`id`-Wert wird ignoriert
- `url` = `"https://www.freelancermap.de" + plink`
- `description` = HTML-Tags gestrippt, Entities dekodiert, Whitespace kollabiert
- `published` = `created` (ISO 8601)

**Fehlerfälle:**
- HTTP-Fehler oder JSON-Insel nicht findbar: `FeedFetchError` werfen, alten State behalten, sauber loggen
- Leere Projekt-Liste: kein Fehler, einfach 0 neue Items mergen

### Datenmodell

Ein Projekt:

```python
{
    "id": str,              # stabiler Hash aus URL
    "title": str,
    "url": str,
    "description": str,     # full text aus RSS description
    "published": str,       # ISO 8601
    "first_seen": str,      # ISO 8601, wann der Crawler das erstmals gesehen hat
    "matched_keywords": list[str],   # welche Positiv-Keywords haben gematcht
    "source": str           # konstant "freelancermap.de" fuer spaetere Erweiterung
}
```

`first_seen` ist NICHT `published`. Ein Projekt kann gestern publiziert worden sein und heute erstmals im Feed auftauchen. Für die NEU-Logik zählt `first_seen`.

### State-Handling

- `data/projects.json` ist die Wahrheit. Bei jedem Crawl-Lauf wird sie geladen, mit neuen Items gemerged, alte aussortiert, wieder geschrieben.
- Items älter als 14 Tage (`first_seen`) werden entfernt, damit die Datei nicht wächst.
- `docs/data.json` ist die public Kopie für das Frontend (gefiltert auf relevante Items).
- Beide Files werden ins Git committed durch die GitHub Action.

### Filterlogik

Konfiguration in `config/keywords.json`:

```json
{
    "positive": [
        "requirements engineer", "anforderungsmanager", "business analyst",
        "projektmanager", "pmo", "scrum master", "product owner",
        "prozessmanager", "testmanager",
        "ireb", "cpre", "iiba", "babok", "agil", "scrum",
        "energie", "evu", "stadtwerke", "netz", "scada", "ems",
        "redispatch", "übertragungsnetz", "tso", "smart meter",
        "marktkommunikation", "edifact"
    ],
    "negative": [
        "java entwickler", "python entwickler", "frontend", "backend",
        "fullstack", "devops engineer", "embedded",
        "togaf", "enterprise architect"
    ]
}
```

**Match-Regeln:**

- Substring-Match, case-insensitive
- Suche in `title + " " + description`
- Qualifiziert: mindestens ein Positiv-Match UND kein Negativ-Match
- `matched_keywords` enthält alle Positiv-Treffer (für UI-Anzeige)

Die Keywords-Datei MUSS extern editierbar bleiben (kein Inline-Hardcoding im Python-Code).

### Repo-Struktur

```
freelancer-scout/
  .github/workflows/
    crawl.yml              # stuendlicher Cron + Deploy
  config/
    keywords.json
  data/
    projects.json          # interner State
  docs/                    # GitHub Pages Source
    index.html             # generiert
    data.json              # gefilterte Projekte fuer Frontend
    style.css
    app.js
    notification.mp3       # NICHT noetig, Sound via Web Audio API
  src/
    __init__.py
    crawler.py             # RSS holen, parsen
    filter.py              # Keyword-Match
    storage.py             # JSON-State laden/speichern
    renderer.py            # HTML aus Jinja-Template
    config.py              # Konstanten, Pfade
  templates/
    index.html.j2
  tests/
    fixtures/
      sample_feed.html       # gespiegeltes Mini-HTML mit JSON-Insel
      sample_projects.json
    test_crawler.py
    test_filter.py
    test_storage.py
    test_renderer.py
    test_smoke.py          # echter HTTP-Call, markiert @smoke
    test_e2e.py            # full pipeline mit Mocks, markiert @e2e
  .gitignore
  README.md
  pytest.ini
  pyproject.toml           # ruff config, deps
  main.py                  # Entry Point: ein Crawl-Lauf
```

### Design Direction

**Aesthetic:** Editorial Reading Layout. Inspiration: gute Online-Magazine und Tools wie Are.na, NYT Cooking, Linear. KEIN Dashboard, KEIN SaaS-Hero, KEIN Bootstrap-Look.

**Fonts (via Google Fonts, im `<head>` einbinden):**

- Display (Titel, Headlines): **Fraunces** (variable serif). Used für Seitentitel und Card-Titel.
- Body: **Manrope** (variable sans). Used für Description und UI-Elemente.
- Mono (Metadaten, Timestamps, IDs): **JetBrains Mono**.

NICHT verwenden: Inter, Roboto, Space Grotesk, System-Fonts, Arial.

**Farbpalette (in CSS Custom Properties, einmal in `:root`, einmal in `@media (prefers-color-scheme: dark)`):**

Light:
- `--bg`: #F5F1E8 (warmes Cream, NICHT pures Weiß)
- `--bg-elevated`: #FBF8F1 (Cards)
- `--ink`: #1A1A1A (Haupttext)
- `--ink-muted`: #6B6B6B (Sekundärtext, Metadaten)
- `--border`: #E5DFCF
- `--accent`: #C0392B (Tomatenrot, NUR für NEU-Badge und kritische Akzente)
- `--keyword-bg`: #2D3D2A (gedämpftes Olivgrün)
- `--keyword-ink`: #F5F1E8

Dark:
- `--bg`: #0F0E0C (warmes Schwarz, NICHT pures Schwarz)
- `--bg-elevated`: #1A1815
- `--ink`: #E8E4D9
- `--ink-muted`: #8A8578
- `--border`: #2A2722
- `--accent`: #E74C3C
- `--keyword-bg`: #4A5A3C
- `--keyword-ink`: #E8E4D9

**Layout:**

- Single-Column, max-width 720px, zentriert. Lesetempo, kein Grid-Wall.
- Generöser Außenrand: 32px mobile, 64px desktop, 96px+ vertical.
- Sticky-Header oben mit Titel + Last-Updated.
- Sticky-Filter-Chip-Leiste direkt drunter, mit subtiler Border-Bottom.
- Cards als separate Blocks mit 24px Gap dazwischen, NICHT als Liste mit Trennlinien.

**Typografie-Hierarchie:**

- Seitentitel: Fraunces 600, 48px desktop / 36px mobile, optical-sizing aktiviert, italic für besonderen Charakter (z.B. nur ein Wort italic).
- Card-Titel: Fraunces 500, 22px, line-height 1.3.
- Body: Manrope 400, 16px, line-height 1.6.
- Metadaten: JetBrains Mono 400, 12px, uppercase NICHT verwenden (lowercase ist ehrlicher).
- Keywords-Chips: Manrope 500, 11px, padding 4px 10px, border-radius 4px (NICHT pill-shape).

**Details, die den Unterschied machen:**

- NEU-Badge: kleines rotes Quadrat (8x8px) links neben dem Titel, mit subtler Pulse-Animation (2s ease-in-out infinite, opacity 1 → 0.4 → 1). NICHT ein großes "NEU"-Wort, sondern ein typografisches Detail.
- Hover auf Card: `background` shift von `--bg-elevated` auf einen leicht wärmeren Ton, 200ms transition. Kein Schatten-Lift, kein Scale.
- Stage-Reveal beim ersten Laden: Cards faden mit staggered delay rein (jede 40ms später), opacity + 8px translate-y.
- Counter im Header: "12 Projekte" als große Fraunces-Zahl, daneben Mono-Text "zuletzt aktualisiert vor 23 Minuten".
- Leerer Zustand: zentrierter Text in Fraunces italic, etwa "Heute noch nichts Spannendes. Komm später wieder."
- Footer: kleine Mono-Zeile mit Source-Hinweis und Link zum Repo.

**Verboten:**

- Lila Gradients
- Glassmorphism / Backdrop-Blur
- Drop-Shadows mit hohem Spread
- Pill-Buttons mit border-radius 9999px
- Hero-Sections mit Riesentitel und "Get Started" Button
- Emojis als UI-Element

**Erlaubt und erwünscht:**

- Subtile Hairline-Borders (1px solid var(--border))
- Asymmetrie: z.B. NEU-Badge bricht aus der Spaltenkante leicht nach links aus
- Mono-Text als Kontrastelement zu Serif
- Italic-Fraunces für Akzente (Counter-Wort, Empty-State)

### Coding Standards

- Type Hints für alle Funktionssignaturen (kein `Any` ohne Begründung).
- Docstrings für alle öffentlichen Funktionen (Google-Style, kurz).
- Eine Datei = eine Verantwortung. `crawler.py` macht NICHT auch Filtering.
- Keine Globals außer Pfad-Konstanten in `config.py`.
- Logging via `logging`-Modul, nicht `print`. Level `INFO` für Standard, `DEBUG` für Detail.
- Exceptions catchen nur dort, wo sie sinnvoll behandelt werden können. Sonst durchpropagieren.
- Strings in deutsch oder englisch, aber konsistent pro Datei. UI deutsch, Code englisch.
- Keine Em Dashes in user-facing Text.

### Test-Standards

- `pytest.ini` mit Markern `smoke` und `e2e`.
- Default-Lauf (`pytest`) führt nur Unit-Tests aus (schnell, deterministisch, keine Netzwerk-Calls).
- `pytest -m smoke` führt Smoke Tests aus (echter HTTP-Call gegen RSS-Feed).
- `pytest -m e2e` führt End-to-End-Tests aus (volle Pipeline, gemockte HTTP-Antwort).
- Coverage-Ziel: >=80% auf `src/`.
- Fixtures liegen in `tests/fixtures/`. Keine Tests gegen Live-Daten außer Smoke.

---

## Phasen

### Phase 0: Projekt-Setup

**Ziel:** Leeres, aber lauffähiges Repo. `pytest` läuft (auch ohne Tests). `ruff` läuft.

**Tasks:**

- Verzeichnisstruktur anlegen (siehe oben).
- `pyproject.toml` mit Dependencies und Ruff-Config.
- `pytest.ini` mit Markern und Discovery-Pfaden.
- `.gitignore` (Python-Standard, `__pycache__`, `.venv`, `.pytest_cache`).
- `README.md` mit Setup-Anweisungen.
- `main.py` als Entry Point, der aktuell nur "Not implemented yet" loggt und mit Exit Code 0 endet.
- Ein Dummy-Test, der einfach `assert True` macht, damit pytest grün ist.

**Definition of Done:**

- `pip install -e .` läuft durch.
- `pytest` läuft grün.
- `ruff check .` läuft sauber.
- `python main.py` läuft ohne Fehler.

**Smoke Test durch Mensch:** keiner. Nach DoD direkt Phase 1.

---

### Phase 1: Crawler MVP

**Ziel:** RSS holen, parsen, in `data/projects.json` schreiben. CLI funktioniert. Noch KEIN Filter, KEIN HTML.

**Tasks:**

- `crawler.py`: Funktion `fetch_feed(url) -> list[RawProject]`. Lädt die HTML-Seite, extrahiert die JSON-Insel, gibt Liste zurück. Bei Netzwerk-Fehler oder fehlender JSON-Insel: `FeedFetchError`.
- `storage.py`: `load_projects(path)`, `save_projects(path, projects)`, `merge_projects(existing, new) -> list`. Merge stempelt `first_seen` auf neue Items, behält es auf bekannten. Entfernt Items älter als 14 Tage.
- ID-Berechnung: SHA-256 der URL, ersten 16 Zeichen. In `crawler.py` als Helper.
- `main.py`: orchestriert load + fetch + merge + save. Logging zeigt Anzahl neu/bekannt/entfernt.
- Tests:
  - `test_crawler.py`: parse-Funktion gegen `fixtures/sample_feed.html` (Mini-HTML mit JSON-Insel und 2-3 synthetischen Projekten). Stabile ID bei gleicher URL.
  - `test_storage.py`: Load/Save Roundtrip. Merge-Logik: neue Items bekommen `first_seen`, alte behalten es, 14-Tage-Cutoff funktioniert.
  - `test_smoke.py`: `@pytest.mark.smoke` echter Call gegen Live-RSS, mindestens 1 Item erwartet.

**Definition of Done:**

- `python main.py` zieht echten Feed, schreibt `data/projects.json` mit echten Daten.
- Zweiter Lauf direkt danach: keine Duplikate, `first_seen` bleibt stabil.
- `pytest` (Unit) grün.
- `pytest -m smoke` grün (sofern Internet verfügbar).

**Smoke Test durch Mensch:**

- `python main.py` ausführen, `data/projects.json` öffnen, prüfen ob sinnvolle Items drinstehen.
- Nochmal ausführen, prüfen ob `first_seen` der bekannten Items unverändert ist.
- Bestätigen oder Probleme melden.

---

### Phase 2: Filter

**Ziel:** Keyword-basierter Filter. CLI gibt zusätzlich `docs/data.json` mit nur relevanten Items aus.

**Tasks:**

- `config/keywords.json` mit der Liste aus dieser Spec anlegen.
- `filter.py`: `load_keywords(path)`, `is_relevant(project, positive, negative) -> bool`, `matched_positives(project, positive) -> list[str]`.
- `main.py` erweitern: nach Save von `projects.json` filtern, gefilterte Items mit `matched_keywords` anreichern, in `docs/data.json` schreiben.
- Tests:
  - `test_filter.py`: Match-Wahrheitstabelle. Positiv-Match alleine → True. Positiv + Negativ → False. Nur Negativ → False. Kein Match → False. Case-insensitive. Multi-Word-Phrase matcht als Phrase. Suche in title und description.
  - Edge: leere Keyword-Liste, fehlende Felder.

**Definition of Done:**

- `python main.py` schreibt `docs/data.json` mit nur relevanten Items, jedes mit `matched_keywords`.
- Tests grün.

**Smoke Test durch Mensch:**

- `docs/data.json` öffnen.
- Prüfen: Sind die Items wirklich relevant für RE/BA/PM im Energiekontext?
- Falls zu viel Müll: Keywords in `config/keywords.json` anpassen, nochmal laufen lassen.
- Bestätigen oder Liste anpassen.

---

### Phase 3: HTML-Frontend

**Ziel:** Lokal öffenbares `docs/index.html` mit den gefilterten Projekten. Mobile-first. NEU-Badge. Sortierung neueste zuerst.

**Tasks:**

- `templates/index.html.j2`: Jinja-Template. Implementiert die unter "Design Direction" definierten Layout-Regeln.
  - `<head>`: Google Fonts (Fraunces, Manrope, JetBrains Mono) preconnect + load.
  - Sticky-Header mit Titel "Freelancer Scout" in Fraunces (ein Wort italic für Charakter), darunter Mono-Zeile mit Counter und Last-Updated.
  - Sticky-Filter-Chip-Leiste.
  - Project-Cards mit NEU-Badge (8x8px Pulse-Quadrat), Titel (Fraunces), Description-Auszug (Manrope, max 300 Zeichen), `matched_keywords` als Chips, `first_seen` relativ als Mono-Text.
  - Footer mit Source-Hinweis und Repo-Link in Mono.
  - Leerer-Zustand-Block (falls keine Items).
- `docs/style.css`: CSS Custom Properties für Light + Dark Mode wie in Design Direction spezifiziert. Mobile-first. Generöse Spacings. Pulse-Keyframe-Animation. Staggered-Reveal-Animation für Cards beim Laden.
- `docs/app.js`: Holt `data.json` (cache-busted via `?t=` Timestamp), rendert Liste, implementiert Filter-Chips. Beim Rendern: setze `animation-delay` pro Card für staggered Reveal. Notification-Logik kommt in Phase 5.
- `renderer.py`: `render(template_path, output_path, context)`. Rendert das Jinja-Template einmal beim Crawl. Hinweis: Wir nutzen das Template als initiales HTML-Skelett. Der eigentliche Inhalt wird per JS aus `data.json` geladen, damit Updates ohne neuen Build sichtbar sind.
- `main.py` erweitern: nach Filter auch `render()` aufrufen, sodass `docs/index.html` existiert.
- Tests:
  - `test_renderer.py`: Template rendert mit Test-Context, Output enthält erwartete Strings und Font-Imports.
  - `test_e2e.py`: `@pytest.mark.e2e` volle Pipeline mit gemocktem RSS-Response, am Ende existieren `data/projects.json`, `docs/data.json`, `docs/index.html`, alle valide.

**Definition of Done:**

- `docs/index.html` lokal im Browser öffnen zeigt die Projekte korrekt.
- Mobile-Ansicht im Browser-DevTools (375px) sieht sauber aus.
- Filter-Chips funktionieren.
- NEU-Badge erscheint bei Items mit `first_seen` < 24h.
- Tests grün.

**Smoke Test durch Mensch:**

- `docs/index.html` im Browser öffnen.
- Desktop und Mobile-View prüfen.
- Filter-Chips ausprobieren.
- Bestätigen oder UI-Anpassungen melden.

---

### Phase 4: GitHub Actions + Pages

**Ziel:** Stündlicher Crawl als GitHub Action. Output wird ins Repo committed. GitHub Pages serviert `docs/`.

**Tasks:**

- `.github/workflows/crawl.yml`:
  - Trigger: `schedule: cron: "0 * * * *"` (stündlich) + `workflow_dispatch` (manuell).
  - Steps: Checkout, Python setup, `pip install -e .`, `python main.py`, Commit + Push der Änderungen in `data/` und `docs/` (mit `[skip ci]` in der Commit-Message).
  - Permissions: `contents: write`.
  - Falls kein Diff: kein Commit (Standard-Verhalten).
- README mit Aktivierungs-Anleitung für GitHub Pages aktualisieren (Settings → Pages → Branch `main` → `/docs`).
- Kein zusätzlicher Test in dieser Phase, da Action-Tests in CI separat liefen würden.

**Definition of Done:**

- Workflow-File committed.
- Erste manuelle Action-Ausführung läuft grün durch.
- Commit mit aktualisierten Files erscheint im Repo.
- Pages-URL zeigt die Seite live.

**Smoke Test durch Mensch:**

- In GitHub: Settings → Pages aktivieren.
- Actions-Tab → "Crawl" → "Run workflow" manuell triggern.
- Warten bis grün.
- Pages-URL aufrufen und prüfen.
- Stündlichen Lauf nach 1-2 Stunden verifizieren.
- Bestätigen oder Probleme melden.

---

### Phase 5: Notifications + Sound

**Ziel:** Bei geöffneter Seite: Browser-Notification + kurzer Beep, wenn neue Items reinkommen.

**Tasks:**

- `docs/app.js` erweitern:
  - Polling alle 5 Minuten via `setInterval`, holt `data.json` neu (cache-busted).
  - Vergleich neuer IDs gegen `localStorage.getItem("seenIds")`.
  - Bei neuen IDs:
    - `Notification` API verwenden (Permission beim ersten Besuch anfragen).
    - Beep via Web Audio API erzeugen (Sinus, 880Hz, 200ms). Eine kleine Helper-Funktion `playBeep()`.
    - Visuell: kurzer Highlight-Effekt auf den neuen Cards (CSS-Animation, einmalig).
  - `seenIds` in `localStorage` updaten.
- Button "Benachrichtigungen aktivieren" sichtbar, solange Permission nicht erteilt wurde.
- Button "Sound testen" für UX-Verifikation.
- Test:
  - `test_e2e.py` erweitern: prüfe dass `app.js` die erwarteten Funktionen exportiert (oder grep auf Funktionsnamen, da kein JS-Test-Setup vorhanden ist).
- README aktualisieren mit Hinweis auf Permission-Anfrage und Tab-offen-Anforderung.

**Definition of Done:**

- Bei manuellem Editieren von `docs/data.json` (neue Item-ID hinzufügen) und Reload triggern Notification + Sound.
- Permission-Flow funktioniert.
- Tests grün.

**Smoke Test durch Mensch:**

- Seite öffnen, Permission erlauben.
- "Sound testen" klicken: Beep hörbar?
- Manuell ein Item in `docs/data.json` hinzufügen, Seite reload: Notification + Sound + Highlight?
- Auf Mobile testen (iOS Safari + Android Chrome).
- Bestätigen oder Probleme melden.

---

## Bekannte Risiken / Hinweise

- **freelance-o-mat-Verfügbarkeit:** Drittseite, kann ausfallen oder Format ändern. Crawler muss bei HTTP-Fehler oder leerem Parse-Ergebnis sauber loggen, nicht abstürzen, alten State erhalten.
- **iOS Safari Notification API:** auf iOS funktioniert Web-Notification nur als installierte PWA. Reine Tab-Notifications fallen auf Sound + visuelles Highlight zurück. Das ist akzeptiert.
- **GitHub Actions Cron-Drift:** Cron-Trigger sind nicht sekundengenau, Verzögerungen von 5-15 Min sind normal. Akzeptiert.
- **localStorage-Limit:** unwahrscheinlich bei <100 IDs, aber `seenIds` regelmäßig auf max. 500 jüngste IDs kappen.

## Nicht-Ziele (explizit ausgeschlossen)

- Keine KI-Bewertung. Keyword-Filter reicht.
- Keine Auth, keine User-Accounts.
- Keine E-Mail-Benachrichtigungen.
- Keine Datenbank.
- Kein Backend-Server. GitHub Pages + Actions reichen.
- Keine Branding-Farben.