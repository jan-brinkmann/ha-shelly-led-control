[English documentation](README.md)

# Shelly LED Control

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Downloads](https://img.shields.io/github/downloads/jan-brinkmann/ha-shelly-led-control/total?label=downloads)](https://github.com/jan-brinkmann/ha-shelly-led-control/releases)
[![Release](https://img.shields.io/github/v/release/jan-brinkmann/ha-shelly-led-control?label=release)](https://github.com/jan-brinkmann/ha-shelly-led-control/releases/latest)
![GitHub commits since latest release](https://img.shields.io/github/commits-since/jan-brinkmann/ha-shelly-led-control/latest)
[![Commit activity](https://img.shields.io/github/commit-activity/m/jan-brinkmann/ha-shelly-led-control)](https://github.com/jan-brinkmann/ha-shelly-led-control/commits/main)
[![Validate](https://github.com/jan-brinkmann/ha-shelly-led-control/actions/workflows/validate.yml/badge.svg)](https://github.com/jan-brinkmann/ha-shelly-led-control/actions/workflows/validate.yml)

`Shelly LED Control` ist eine lokale benutzerdefinierte Home-Assistant-Integration. Sie stellt die Status-LED eines Shelly Plus Plug S als einfache Ein/Aus-Lichtentität bereit. Sie ist für den parallelen Betrieb mit der offiziellen Shelly-Integration gedacht und ersetzt diese nicht.

## Unterstütztes Gerät

- Der Shelly Plus Plug S (`SNPL-00112EU`) ist das primär unterstützte Gerät.
- Andere Shelly Wall Plugs können funktionieren, wenn ihre lokale Gen2+-RPC-API die Komponente `PLUGS_UI` mit `PLUGS_UI.GetConfig` und `PLUGS_UI.SetConfig` bereitstellt.

## Aktuelle Funktionen

- Eine `light`-Entität namens **Status-LED** für jedes eingerichtete Shelly.
- `light.turn_on` aktiviert die LED-Anzeige und `light.turn_off` deaktiviert sie.
- `mode: off` sowie ein aktiver Nachtmodus mit Helligkeit null werden als aus angezeigt; der Zustand nutzt die lokale Uhrzeit des Shellys und aktualisiert sich an den Grenzen des Zeitfensters.
- Ein Konfigurationsschalter **Nachtmodus** sowie die Zeit-Entitäten **Beginn Nachtmodus** und **Ende Nachtmodus**.
- Das Zeitfenster des Nachtmodus wird als lokale Shelly-Start- und Endzeit im Format `HH:MM` geschrieben, ohne die konfigurierte Helligkeit zu verändern.
- Nutzt lokale asynchrone Shelly-RPC, Digest-Authentifizierung bei aktivierter Anmeldung, Push-Ereignisse und eine Aktualisierung alle fünf Minuten als Rückfallebene.
- Unterstützt mehrere Geräte mit stabilen, MAC-adressbasierten eindeutigen IDs.

## Installation

### Empfohlen: HACS

1. Installiere bei Bedarf [HACS](https://hacs.xyz).
2. Öffne **HACS**, wähle im Drei-Punkte-Menü **Benutzerdefinierte Repositories** und füge `https://github.com/jan-brinkmann/ha-shelly-led-control` als **Integration** hinzu.
3. Lade **Shelly LED Control** herunter, starte Home Assistant neu und füge die Integration unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** hinzu.

### Manuelle Installation

1. Kopiere `custom_components/shelly_led_control` nach `<configuration_directory>/custom_components/shelly_led_control`.
2. Starte Home Assistant neu und füge **Shelly LED Control** unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** hinzu.

## Konfiguration

Gib Hostname oder IP-Adresse des Shelly ein. Die Integration prüft die lokale Verbindung und das Vorhandensein von `PLUGS_UI`, bevor ein Eintrag angelegt wird. Shelly-Gen2-Geräte verwenden normalerweise `admin`; lasse das Passwort leer, wenn die Geräteauthentifizierung deaktiviert ist, andernfalls gib das Gerätepasswort ein. Home Assistant speichert Zugangsdaten im Konfigurationseintrag und schreibt sie niemals in Logs.

Richte jedes physische Shelly separat ein. Die von der Shelly-API gelieferte MAC-Adresse dient als stabile Eintrags- und Entitätskennung, sodass ein DHCP-Adresswechsel keine neue Entität erzeugt.

## Verwendung

Verwende die **Status-LED** wie jedes Ein/Aus-Licht in Dashboards, Automatisierungen, Szenen oder über `light.turn_on` und `light.turn_off`.

- **Aus** schreibt `PLUGS_UI.leds.mode: off`.
- **An** stellt den zuletzt beobachteten Nicht-Aus-Modus wieder her, solange diese Integration läuft. Nach einem Home-Assistant-Neustart bei deaktivierter LED wird `switch` als stabiler aktivierter Modus verwendet.

Die vollständige aktuelle `PLUGS_UI`-Konfiguration wird vor jedem Schreiben gelesen. Nur `leds.mode` oder das angeforderte Feld von `leds.night_mode` ändert sich; konfigurierte Farben, Helligkeit und Steuerungen bleiben erhalten.

Verwende den Schalter **Nachtmodus** im Konfigurationsbereich des Geräts, um den Shelly-Nachtmodus zu aktivieren oder zu deaktivieren. Über **Beginn Nachtmodus** und **Ende Nachtmodus** legst du das lokale Zeitfenster fest. Die Integration bietet keine Einstellung für die Nachtmodus-Helligkeit; Änderungen am Schalter oder an den Zeiten behalten die auf dem Shelly konfigurierte Helligkeit bei.

## Aktuelle Einschränkungen

Version 1.0.0 unterstützt LED an/aus sowie das Aktivieren, Deaktivieren und Planen des Nachtmodus. RGB-Farbe, Helligkeit, getrennte Auswahl von LED-Modi, leistungsabhängige Anzeige und automatische Erkennung sind nicht implementiert. `PLUGS_UI` hat keinen eigenen Live-Status; die Entität leitet den wirksamen LED-Zustand daher aus dem konfigurierten Modus und dem Zeitplan eines Nachtmodus mit Helligkeit null ab, statt das ausgestrahlte Licht direkt zu messen.

## Kompatibilität

Die Integration nutzt einen separaten Konfigurationseintrag und eine MAC-adressbasierte Geräte-Registry-Verbindung. Nach den aktuellen Regeln der Home-Assistant-Geräte-Registry ist die Geräteidentität auf den besitzenden Konfigurationseintrag begrenzt. Eine Entität dieser Custom Integration kann daher nicht sicher in den Geräte-Eintrag der offiziellen Shelly-Integration eingefügt werden. Home Assistant zeigt deshalb einen separaten, von dieser Integration verwalteten Geräte-Eintrag für denselben physischen Plug; die offizielle Shelly-Integration verwaltet ihre bestehenden Entitäten weiterhin ohne Kollision. Siehe [Architektur](docs/architecture.md).

## Fehlerbehebung

- Stelle sicher, dass das Gerät von Home Assistant erreichbar und seine lokale RPC-API aktiviert ist.
- Stelle sicher, dass das Gerät `PLUGS_UI` bereitstellt und unterstützte Plus-Plug-S-Firmware verwendet.
- Bei aktivierter Authentifizierung öffne die erneute Anmeldung der Integration und gib die aktuellen `admin`-Zugangsdaten ein.
- Wirkt der LED-Zustand nach Änderungen in der Geräte-Weboberfläche veraltet, warte kurz auf das Push-Ereignis `config_changed` oder die Aktualisierung nach fünf Minuten.

## Aktualisierung

Aktualisiere über HACS und starte Home Assistant neu, wenn dies angefordert wird. Bei manueller Installation ersetze nur `custom_components/shelly_led_control` und starte Home Assistant neu. Bestehende Konfigurationseinträge bleiben erhalten.

## Geplante Funktionen

Künftige Versionen können RGB-Farbe, Helligkeit, explizite Auswahl von LED-Modi, leistungsabhängige Anzeige, automatische Erkennung und weitere Shelly-Modelle ergänzen. Keine dieser Funktionen ist in v1 implementiert.

## Lizenz

Dieses Projekt steht unter der [MIT-Lizenz](LICENSE).
