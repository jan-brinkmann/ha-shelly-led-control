[English documentation](README.md)

# Shelly LED Control

Mit **Shelly LED Control** steuerst du die Status-LEDs kompatibler Shelly-Steckdosen in Home Assistant. Je nach Modell kannst du die Anzeige schalten, Farbe und Helligkeit einstellen oder den Nachtmodus planen. Die Integration arbeitet lokal und ergänzt die Shelly- und Z-Wave-JS-Integrationen von Home Assistant.

## Funktionen

- Status-LED ein- und ausschalten, auch über Dashboards, Szenen und Automatisierungen.
- LED-Anzeige nach Leistungsaufnahme oder Ein/Aus-Zustand der Steckdose wählen.
- Eigene Farben und Helligkeiten für die eingeschaltete und ausgeschaltete Steckdose festlegen.
- Nachtmodus planen, um die LED nachts zu dimmen oder auszuschalten.
- Aktuelle LED-Helligkeit und Nachtmodus-Status anzeigen, mit Helligkeitsverlauf in Home Assistant.

![Shelly LED Control Banner](docs/banner.png)

[![Downloads](https://img.shields.io/github/downloads/jan-brinkmann/ha-shelly-led-control/total?label=downloads)](https://github.com/jan-brinkmann/ha-shelly-led-control/releases)
[![Release](https://img.shields.io/github/v/release/jan-brinkmann/ha-shelly-led-control?label=release)](https://github.com/jan-brinkmann/ha-shelly-led-control/releases/latest)

## Unterstützte Geräte

| Shelly-Modell | LED-Funktionen |
| --- | --- |
| Plus Plug S (v1 und v2), Plus Plug UK, Plug S (MTR) Gen3, AZ Plug, Outdoor Plug S Gen3, Plug M Gen3, Plug US Gen4 | Ein/Aus, Anzeige nach Leistungsaufnahme oder Schaltzustand, RGB und Helligkeit pro Relaiszustand, Nachtmodus mit Zeitplan, Helligkeits- und Nachtmodus-Sensoren. |
| Plug PM Gen3 | Ein/Aus, Anzeige nach Leistungsaufnahme oder benutzerdefinierter Farbe, Helligkeit, Nachtmodus mit Zeitplan und die zugehörigen Sensoren. Die dauerhaft aktive Steckdose hat ein RGB- und Helligkeitsprofil. |
| Plug, Plug E, Plug S, Plug US (Gen1) | Getrennte Ein/Aus-Steuerung der Netzwerk- und Schaltzustandsanzeige, je nach verfügbaren Firmware-Einstellungen. |
| Wave Plug S, Wave Plug UK, Wave Plug US, Wave Outdoor Plug S, einschließlich LR-Varianten | Ein/Aus und Dimmen über Z-Wave JS, sofern die Firmware den Helligkeitsparameter 105 bereitstellt. |

Plus Plug IT, Plus Plug US und Plug CN Gen3 haben Status-LEDs. Die öffentlichen Shelly-APIs dokumentieren für diese Geräte keine LED-Steuerung.

<!-- ha-marketplace:exclude-start -->

## Installation

### Über den Marketplace

[![Shelly LED Control im Home Assistant Marketplace öffnen](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=jan-brinkmann&repository=ha-shelly-led-control&category=integration)

1. Öffne das Repository über die Schaltfläche oben. Alternativ wähle **Einstellungen → Marketplace → Über Link hinzufügen** und gib `https://github.com/jan-brinkmann/ha-shelly-led-control` ein.
2. Verbinde beim Hinzufügen dein GitHub-Konto, wenn der Marketplace dich dazu auffordert. Wähle **Integration**, falls der Typ abgefragt wird.
3. Wähle auf der Seite **Shelly LED Control** die Option **Installieren**. Sobald die Integration bereit ist, öffnet Home Assistant die Einrichtung.

### Manuelle Installation

1. Lade das Quellcode-Archiv der [neuesten Version](https://github.com/jan-brinkmann/ha-shelly-led-control/releases/latest) herunter und entpacke es.
2. Kopiere den Ordner `custom_components/shelly_led_control` in den Ordner `custom_components` deiner Home-Assistant-Konfiguration.
3. Starte Home Assistant neu.

<!-- ha-marketplace:exclude-end -->

## Einrichtung

1. Öffne **Einstellungen → Geräte & Dienste → Integration hinzufügen** und wähle **Shelly LED Control**.
2. Gib für eine WLAN-Steckdose den lokalen Hostnamen oder die IP-Adresse ein. Wenn der Anmeldeschutz aktiv ist, gib die Zugangsdaten des Geräts ein. Der Standardbenutzername ist `admin`.
3. Binde eine Wave-Steckdose zuerst in **Z-Wave JS** ein. Wähle dann in Shelly LED Control **Wave-Steckdose (Z-Wave JS)** und anschließend das gekoppelte Gerät.

Wiederhole die Einrichtung für jeden weiteren Shelly. Geräte werden manuell hinzugefügt.

## Verwendung

Öffne das Gerät unter **Einstellungen → Geräte & Dienste → Shelly LED Control**. Die Bedienelemente kannst du auch in Dashboards, Szenen und Automatisierungen nutzen.

| Bedienelement | Was du damit machst |
| --- | --- |
| **Status-LED** | LED-Anzeige ein- oder ausschalten. Bei Wave-Steckdosen lässt sich hier auch die Helligkeit einstellen. |
| **Netzwerk-LED / Schaltzustands-LED** | Die jeweilige Anzeige bei einer Gen1-Steckdose aktivieren oder deaktivieren. Der Zustand zeigt die Einstellung an. |
| **LED-Anzeigemodus** | **Leistungsaufnahme** oder **Schaltzustand** wählen. Die Auswahl aktiviert die LED-Anzeige. |
| **LED-Farbe bei Relais an / aus** oder **Benutzerdefinierte LED-Farbe** | Farbe und Helligkeit im jeweiligen Anzeigemodus einstellen. Beim Plug PM Gen3 gibt es ein Profil im Modus **Benutzerdefinierte Farbe**. |
| **Helligkeit Normalbetrieb** | Helligkeit außerhalb des Nachtmodus von 0 bis 100 % einstellen. Im Modus **Schaltzustand** gilt die Änderung für den aktuellen Ein/Aus-Zustand der Steckdose. |
| **Nachtmodus nutzen** | Zeitplan für den Nachtmodus aktivieren. |
| **Beginn / Ende Nachtmodus** und **Helligkeit Nachtmodus** | Zeitfenster und Helligkeit festlegen. Bei 0 % bleibt die LED während des Nachtmodus aus. |
| **Nachtmodus aktiv** | Prüfen, ob der geplante Nachtmodus gerade aktiv ist. |
| **Dimmwert Status-LED** | Aktuelle Helligkeit in Prozent einschließlich Nachtmodus und den Verlauf ansehen. |

Im Modus **Leistungsaufnahme** wählt Shelly die Farbe automatisch. Bei Geräten mit Relais erlischt die Leistungsanzeige, wenn das Relais ausgeschaltet ist. Beim Plug PM Gen3 ist die Steckdose dauerhaft aktiv.

Der Nachtmodus richtet sich nach der lokalen Uhrzeit des Shelly und kann über Mitternacht laufen. **Dimmwert Status-LED** wird aus den Geräteeinstellungen und dem Gerätezustand berechnet.

Wenn du auch die offizielle Shelly-Integration nutzt, zeigt Home Assistant einen separaten Geräteeintrag für die LED-Steuerung. Das ist normal.

## Hilfe

- **Keine Verbindung?** Prüfe, ob der Shelly online und seine Weboberfläche aus dem Netzwerk von Home Assistant erreichbar ist.
- **Anmeldung fehlgeschlagen?** Prüfe das Gerätepasswort und nutze die erneute Anmeldung in Home Assistant, wenn sie angeboten wird.
- **Nachtmodus-Status unbekannt?** Prüfe, ob die Uhrzeit des Shelly korrekt eingestellt ist.
- **Einstellungen in der Shelly-Weboberfläche geändert?** Sie werden automatisch in Home Assistant übernommen; bei verzögerter Aktualisierung kann das bis zu fünf Minuten dauern.

Technische Hintergründe findest du unter [Technische Entscheidungen](docs/architecture.md) (Englisch).

## Lizenz

Veröffentlicht unter der [MIT-Lizenz](LICENSE).
