# Freelancer Scout

Stuendlicher Crawler fuer freelancermap.de, der relevante Projekte filtert und auf einer statischen Webseite (GitHub Pages) anzeigt.

## Setup

Voraussetzung: Python 3.11+.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -e ".[dev]"
```

## Verwendung

Einmaliger Crawl-Lauf:

```bash
python main.py
```

## Entwicklung

Tests (Unit, schnell, keine Netzwerk-Calls):

```bash
pytest
```

Smoke Tests (echter HTTP-Call gegen Live-Feed):

```bash
pytest -m smoke
```

End-to-End-Tests (volle Pipeline mit Mocks):

```bash
pytest -m e2e
```

Linter und Formatter:

```bash
ruff check .
ruff format .
```

## Deployment auf GitHub Pages

Einmalig nach dem ersten lokalen Lauf:

**1. Repo auf GitHub anlegen und pushen**

```powershell
git init
git add .
git commit -m "initial commit"
git branch -M main
# Variante a) mit GitHub CLI:
gh repo create freelancer-scout --public --source=. --push
# Variante b) manuell: leeres Repo auf github.com anlegen, dann:
#   git remote add origin https://github.com/<dein-user>/freelancer-scout.git
#   git push -u origin main
```

**2. Pages aktivieren**

Im Repo: **Settings → Pages**
- Source: *Deploy from a branch*
- Branch: `main`, Folder: `/docs`
- Save

**3. Workflow-Permissions**

Im Repo: **Settings → Actions → General → Workflow permissions**
- *Read and write permissions* auswählen

**4. Ersten Lauf manuell triggern**

Im Repo: **Actions → Crawl → Run workflow → main → Run workflow**

Nach ~30 Sekunden grün. Der Bot-Commit aktualisiert `data/projects.json` und `docs/` mit dem ersten Lauf-Stand.

**5. Live aufrufen**

`https://<dein-user>.github.io/freelancer-scout/`

Ab jetzt läuft der Crawler stündlich (Cron `0 * * * *`, GitHub kann 5-15 min driften). Manuelle Läufe weiterhin über den Actions-Tab.

## Benachrichtigungen

Solange die Seite in einem offenen Tab läuft, pollt sie alle 5 Minuten `data.json`. Tauchen neue Projekte auf, gibt es:

- eine Browser-Notification (sofern erlaubt),
- einen kurzen Beep (Web Audio API),
- einen einmaligen Highlight-Effekt auf den neuen Cards.

Hinweise:

- **Permission:** Beim ersten Besuch erscheint der Button „Benachrichtigungen aktivieren". Erst nach Erlauben kommen Notifications. Der Button „Sound testen" prüft den Beep.
- **Tab muss offen bleiben:** Es gibt keinen Push-Dienst im Hintergrund. Live-Benachrichtigungen funktionieren nur bei geöffnetem Tab.
- **Autoplay-Politik:** Der Beep braucht eine vorherige Interaktion mit der Seite (einmal „Sound testen" oder „Benachrichtigungen aktivieren" klicken). Danach klingt er bei neuen Treffern.
- **iOS Safari:** Web-Notifications funktionieren dort nur als installierte PWA. Im normalen Tab fällt die Seite auf Sound + visuelles Highlight zurück. Das ist akzeptiert.

## Projektstatus

Aktueller Stand: Phasen 0-5 implementiert.
