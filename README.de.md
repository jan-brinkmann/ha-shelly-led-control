[English documentation](README.md)

# Shelly LED Control

![Shelly LED Control Banner](docs/banner.png)

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Downloads](https://img.shields.io/github/downloads/jan-brinkmann/ha-shelly-led-control/total?label=downloads)](https://github.com/jan-brinkmann/ha-shelly-led-control/releases)
[![Release](https://img.shields.io/github/v/release/jan-brinkmann/ha-shelly-led-control?label=release)](https://github.com/jan-brinkmann/ha-shelly-led-control/releases/latest)
![GitHub commits since latest release](https://img.shields.io/github/commits-since/jan-brinkmann/ha-shelly-led-control/latest)
[![Commit activity](https://img.shields.io/github/commit-activity/m/jan-brinkmann/ha-shelly-led-control)](https://github.com/jan-brinkmann/ha-shelly-led-control/commits/main)
[![Validate](https://github.com/jan-brinkmann/ha-shelly-led-control/actions/workflows/validate.yml/badge.svg)](https://github.com/jan-brinkmann/ha-shelly-led-control/actions/workflows/validate.yml)

`Shelly LED Control` ist eine lokale benutzerdefinierte Home-Assistant-Integration zur Konfiguration der Status-LED eines Shelly Plus Plug S. Sie bietet Ein/Aus-Steuerung, Modusauswahl, Farben für die Relaiszustände und Helligkeitseinstellungen. Sie ist für den parallelen Betrieb mit der offiziellen Shelly-Integration gedacht und ersetzt diese nicht.

## Unterstütztes Gerät

- Der Shelly Plus Plug S (`SNPL-00112EU`) ist das primär unterstützte Gerät.
- Andere Shelly Wall Plugs können funktionieren, wenn ihre lokale Gen2+-RPC-API die Komponente `PLUGS_UI` mit `PLUGS_UI.GetConfig` und `PLUGS_UI.SetConfig` bereitstellt.

## Aktuelle Funktionen

- Eine `light`-Entität namens **Status-LED** für jedes eingerichtete Shelly.
- `light.turn_on` aktiviert die LED-Anzeige und `light.turn_off` deaktiviert sie.
- Eine Konfigurationsauswahl **LED-Anzeigemodus** mit **Leistungsaufnahme** und **Schaltzustand**.
- Zwei RGB-Konfigurationslichter **LED-Farbe bei Relais an** und **LED-Farbe bei Relais aus** für separate Farben und normale Helligkeiten im Modus **Schaltzustand**.
- `mode: off` sowie eine wirksame Helligkeit von null werden als aus angezeigt; der Zustand nutzt die lokale Uhrzeit des Shellys und aktualisiert sich an den Grenzen des Zeitfensters.
- Im Modus **Leistungsaufnahme** führt ein ausgeschaltetes Relais zu 0 % wirksamer Helligkeit und einer ausgeschalteten **Status-LED**, auch während des Nachtmodus; der gespeicherte normale Dimmwert bleibt erhalten.
- Ein Konfigurationsschalter **Nachtmodus nutzen** sowie die Zeit-Entitäten **Beginn Nachtmodus** und **Ende Nachtmodus**.
- Ein schreibgeschützter Binärsensor **Nachtmodus aktiv**, der eingeschaltet ist, wenn der Nachtmodus genutzt wird und die lokale Shelly-Uhrzeit im konfigurierten Zeitfenster liegt, unabhängig von der Helligkeit.
- Ein schreibgeschützter Sensor **Dimmwert Status-LED** für die aktuell wirksame Helligkeit von 0 bis 100 %, einschließlich Nachtmodus, mit Verlauf und Langzeitstatistik in Home Assistant.
- Eine Zahl-Entität **Helligkeit Nachtmodus** im Konfigurationsbereich mit 0 bis 100 % in Schritten von 1 %.
- Eine Zahl-Entität **Helligkeit Normalbetrieb** im Konfigurationsbereich mit 0 bis 100 % in Schritten von 1 % für den aktuellen LED-Modus und Relaiszustand außerhalb des Nachtmodus.
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

Mit **LED-Anzeigemodus** im Konfigurationsbereich des Geräts wählst du **Leistungsaufnahme** (`power`, in der Shelly-WebUI „Power consumption“) oder **Schaltzustand** (`switch`, „Switch state“). Die Auswahl aktiviert die LED-Anzeige. Zum vollständigen Ausschalten nutzt du weiterhin das Licht **Status-LED**. Bei ausgeschalteter Anzeige zeigt die Modusauswahl **Unbekannt**, da keiner der beiden aktiven Modi ausgewählt ist; du kannst trotzdem einen Modus wählen und die Anzeige damit wieder einschalten. Änderungen in der Shelly-WebUI aktualisieren auch die Auswahl.

Im Modus **Schaltzustand** öffnest du **LED-Farbe bei Relais an** und **LED-Farbe bei Relais aus**, um über den Home-Assistant-Farbwähler beide Farben getrennt einzustellen. Diese Konfigurationslichter bearbeiten die gespeicherten Einstellungen; das Relais der Steckdose wird dabei nicht geschaltet. Ihre Helligkeitsregler ändern die normale Helligkeit für jeden Zustand separat, auch für den gerade nicht aktiven Zustand. Eine reine Farbänderung erhält dessen Dimmwert und alle Nachtmodus-Einstellungen. Der Ein/Aus-Zustand des Konfigurationslichts bezieht sich auf seinen normalen Dimmwert, unabhängig von Relaiszustand und Nachtmodus. Ausschalten setzt nur dessen Helligkeit auf 0 %. Einschalten ohne Farb- oder Helligkeitsangabe setzt einen Dimmwert von 0 % wieder auf 100 %; Einschalten mit ausschließlich einer Farbangabe erhält auch einen Dimmwert von 0 %. Außerhalb des Modus **Schaltzustand** sind beide Konfigurationslichter **Nicht verfügbar**. Im Modus **Leistungsaufnahme** bestimmt Shelly die Farbe automatisch anhand des Verbrauchs; die normale Helligkeit lässt sich weiterhin einstellen. Siehe [Shelly-Konfigurationsschema](https://shelly-api-docs.shelly.cloud/gen2/Devices/Gen2/ShellyPlusPlugS/).

Die vollständige aktuelle `PLUGS_UI`-Konfiguration wird vor jedem Schreiben gelesen. Nur das angeforderte Feld `leds.mode`, der RGB-/Helligkeitswert in `leds.colors` oder ein Feld von `leds.night_mode` ändert sich; alle übrigen Einstellungen einschließlich Farbe und Helligkeit des anderen Relaiszustands sowie der Tastensteuerung bleiben erhalten. Nach erfolgreichen Dienstaufrufen werden alle Entitäten sofort neu vom Gerät eingelesen, auch bei unmittelbar aufeinanderfolgenden Änderungen.

Mit **Helligkeit Normalbetrieb** im Konfigurationsbereich des Geräts stellst du die Helligkeit außerhalb des Nachtmodus von 0 bis 100 % ein. Im LED-Modus `power` ändert sich die Helligkeit der Leistungsanzeige. Im Modus `switch` ändert sich nur der Wert für den aktuellen Relaiszustand (an oder aus); die Helligkeit des anderen Zustands bleibt erhalten. Die Einstellung folgt Änderungen des LED-Modus und Relaiszustands. Sie zeigt auch während eines aktiven Nachtmodus den normalen Helligkeitswert, sodass du die Helligkeit für danach vorbereiten kannst. Nachtmodus-Helligkeit und Zeitplan bleiben erhalten. Bei 0 % ist die LED außerhalb des Nachtmodus aus. Bei deaktivierter LED-Anzeige (`mode: off`) oder einem nicht unterstützten Modus ist die Einstellung **Nicht verfügbar**. Fehlt der Helligkeitswert oder ist der Relaiszustand unbekannt, lautet der Wert **Unbekannt**. Der Wert lässt sich auch in Automatisierungen über `number.set_value` ändern.

Mit dem Schalter **Nachtmodus nutzen** im Konfigurationsbereich des Geräts legst du fest, ob der Shelly-Nachtmodus genutzt wird. Ein eingeschalteter Schalter aktiviert den Zeitplan; er zeigt nicht an, ob der Nachtmodus gerade aktiv ist. Über **Beginn Nachtmodus** und **Ende Nachtmodus** legst du das lokale Zeitfenster fest. Mit **Helligkeit Nachtmodus** stellst du die gewünschte LED-Helligkeit von 0 bis 100 % ein; 0 % schaltet die LED während des aktiven Nachtmodus-Zeitfensters aus. Der Wert lässt sich auch in Automatisierungen über `number.set_value` ändern. Eine Änderung der Helligkeit behält den Ein/Aus-Zustand des Nachtmodus und das Zeitfenster bei; Änderungen am Schalter oder an den Zeiten behalten die konfigurierte Helligkeit bei.

**Nachtmodus aktiv** ist eine reine Statusanzeige: **An** bedeutet, dass der Nachtmodus genutzt wird und die lokale Shelly-Uhrzeit im Zeitfenster liegt; ansonsten ist der Status **Aus**. Der Status gilt bei jeder Nachtmodus-Helligkeit und auch bei ausgeschaltetem LED-Anzeigemodus. Er aktualisiert sich zum Beginn und Ende des Zeitfensters. Die Startzeit gehört zum Zeitfenster, die Endzeit nicht; Zeitfenster über Mitternacht werden unterstützt. Wird der Nachtmodus genutzt, aber die Shelly-Uhr ist noch nicht synchronisiert, lautet der Status **Unbekannt**. Der umbenannte Schalter behält bei bestehenden Installationen seine Entitäts-ID.

**Dimmwert Status-LED** zeigt die aktuell wirksame Helligkeit in Prozent. Bei ausgeschaltetem LED-Anzeigemodus sind es 0 %. Im Modus **Leistungsaufnahme** führt auch ein ausgeschaltetes Relais zu 0 %, einschließlich des Nachtmodus. Die Einstellung **Helligkeit Normalbetrieb** zeigt weiterhin den gespeicherten Wert für das nächste Einschalten. Bei eingeschaltetem Relais bedeutet 0 Watt hingegen nicht 0 % Helligkeit: Shelly stellt eine Last von null durch eine grüne LED dar. Ansonsten gilt im aktiven Nachtmodus dessen Helligkeit. Außerhalb des Nachtmodus verwendet der Sensor die Helligkeit des LED-Modus `power` oder im Modus `switch` die zum aktuellen Relaiszustand gehörende Helligkeit. Er aktualisiert sich bei Konfigurations- und Relaisänderungen sowie an den Grenzen des Nachtmodus. Der Wert wird aus den von Shelly gemeldeten Einstellungen und Zuständen berechnet; er ist keine Messung des ausgestrahlten Lichts. Siehe [Shelly-LED-Verhalten](https://kb.shelly.cloud/knowledge-base/shelly-plus-plug-s-v2) und [Shelly-API](https://shelly-api-docs.shelly.cloud/gen2/Devices/Gen2/ShellyPlusPlugS/).

Home Assistant zeichnet den Sensor im Verlauf auf, sofern er nicht über die Recorder-Konfiguration ausgeschlossen ist. Die Zustandsklasse `measurement` ermöglicht außerdem Langzeitstatistiken. Fehlen benötigte Helligkeitswerte oder der Relaiszustand, oder ist bei genutztem Nachtmodus die Shelly-Uhr noch nicht synchronisiert, bleibt der Wert **Unbekannt**. Ein im Leistungsmodus ausgeschaltetes Relais führt auch ohne synchronisierte Uhr zu 0 %. Bei unbekanntem Relaiszustand wird im Leistungsmodus keine positive Helligkeit angezeigt; ein bekannter Dimmwert von null ergibt weiterhin 0 %. Bei unterbrochener Geräteverbindung ist er **Nicht verfügbar**.

## Aktuelle Einschränkungen

Die Integration unterstützt LED an/aus, die Auswahl zwischen leistungs- und schaltzustandsabhängiger Anzeige, separate RGB-Farben und Helligkeiten für beide Relaiszustände, die Anzeige und Aufzeichnung des wirksamen Dimmwerts, das Einstellen der normalen Helligkeit sowie das Aktivieren, Deaktivieren, Planen und Einstellen der Helligkeit des Nachtmodus. Eigene Zuordnungen zwischen Leistung und Farbe sowie automatische Erkennung sind nicht implementiert. `PLUGS_UI` hat keinen eigenen Live-Status; die Entitäten leiten den LED-Zustand daher aus den Einstellungen und Gerätezuständen ab. Die Konfigurationslichter zeigen gespeicherte Einstellungen und keine gemessene Lichtausgabe.

## Kompatibilität

Die Integration nutzt einen separaten Konfigurationseintrag und eine MAC-adressbasierte Geräte-Registry-Verbindung. Nach den aktuellen Regeln der Home-Assistant-Geräte-Registry ist die Geräteidentität auf den besitzenden Konfigurationseintrag begrenzt. Eine Entität dieser Custom Integration kann daher nicht sicher in den Geräte-Eintrag der offiziellen Shelly-Integration eingefügt werden. Home Assistant zeigt deshalb einen separaten, von dieser Integration verwalteten Geräte-Eintrag für denselben physischen Plug; die offizielle Shelly-Integration verwaltet ihre bestehenden Entitäten weiterhin ohne Kollision. Siehe [Architektur](docs/architecture.md).

## Fehlerbehebung

- Stelle sicher, dass das Gerät von Home Assistant erreichbar und seine lokale RPC-API aktiviert ist.
- Stelle sicher, dass das Gerät `PLUGS_UI` bereitstellt und unterstützte Plus-Plug-S-Firmware verwendet.
- Bei aktivierter Authentifizierung öffne die erneute Anmeldung der Integration und gib die aktuellen `admin`-Zugangsdaten ein.
- Änderungen in der Geräte-Weboberfläche, auch reine RGB-Farbänderungen, aktualisieren die Entitäten über `config_changed`-Ereignisse von `plugs_ui` oder Änderungen von `sys.cfg_rev` in Statusmeldungen. Die Erkennung des Komponentennamens berücksichtigt beide Schreibweisen in Groß- und Kleinbuchstaben. Bei verpassten Meldungen liest die Aktualisierung nach fünf Minuten die aktuellen Einstellungen erneut ein.
- Scheitert der Start mit `No module named 'aioshelly.json'`, aktualisiere alle Integrationsdateien einschließlich `manifest.json` und starte Home Assistant Core vollständig neu. Diese Integration nutzt die von der offiziellen Shelly-Integration verwaltete `aioshelly`-Version und installiert keine eigene Version. Ein Neuladen allein entfernt keine Python-Module, die während des Starts bereits geladen wurden.

## Aktualisierung

Aktualisiere über HACS und starte Home Assistant neu, wenn dies angefordert wird. Bei manueller Installation ersetze nur `custom_components/shelly_led_control` und starte Home Assistant neu. Bestehende Konfigurationseinträge bleiben erhalten.

## Geplante Funktionen

Künftige Versionen können automatische Erkennung und weitere Shelly-Modelle ergänzen. Diese Funktionen sind noch nicht implementiert.

## Lizenz

Dieses Projekt steht unter der [MIT-Lizenz](LICENSE).
