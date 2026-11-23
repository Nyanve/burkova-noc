# Búrková noc – čo sa stalo

Zdroj: `predictions_night1.csv` (eval z `classify.py`: 60/60 na `labeled_sample.jsonl`, 99,97 % na syntetickej „druhej noci“), `calls.csv`, `oms_api_metrics.txt`. Časy sú lokálne (UTC+1). Podrobnosti sú v prílohách A a B.

## 2. Čísla

**Čo znamená „38 %“.** Je to podiel hovorov s `ended_by = bot` (4 332 z 11 400). Hovorí, kto zložil, nie či bot pomohol. **7 z 10 z nich (3 028)** sú bežné rozlúčky po oznámení poruchy a odhadu obnovy. V čísle sa klientka mýli, v podstate má pravdu: pri každom zlyhaní bot naozaj „len zložil“, lebo nemá náhradný postup.

| Výsledok (11 400 hovorov, 10 300 ľudí) | hovory | % |
|---|---:|---:|
| Pomohol: porucha + odhad / hlásenie / dispečing / odkázal inam | 9 120 | 80 % |
| **Reálne zlyhanie** | **1 368** | **12 %** |
| ↳ `API_ERROR`: systém výpadkov Voltiky (OMS) neodpovedal, 60× `create_ticket` | 684 | 6 % |
| ↳ `ADDRESS_NOT_UNDERSTOOD` | 456 | 4 % |
| ↳ `TRANSFER_FAILED`: nebezpečná situácia, dispečing neprijal | 228 | 2 % |
| `ENDED_EARLY`: 639 zložilo pred adresou, 273 počas čakania na OMS | 912 | 8 % |

**Prečo:**
- **API_ERROR je jeden incident.** 620 zo 684 padlo medzi 21:40 a 22:30. OMS sa vtedy skokovo spomalil (medián 1 s → 6 s) a ~30 % dopytov zlyhalo, hoci záťaž sa nezmenila. Príčina je u Voltiky a nevieme ju (príloha A). Bot čakal 8 s, ospravedlnil sa a zložil. To je naše.
- **Adresy** zlyhávajú celú noc rovnako, s búrkou nesúvisia. ASR rozdelí slová („se nec“, „tridsa ťštyri“), problémom sú aj časti obcí (Grinava, Cajla), ulice s číslom („29. augusta“) a „lomeno“. 60× resolver vrátil dvakrát tú istú zlú adresu.
- **Prepojenia:** 228 z 1 026 hlásení nebezpečnej situácie (22 %) sa k dispečerovi nedostalo (160× plný front s limitom 10, 68× nikto nezdvihol). Bot povedal „zavolajte znova“. **Najvážnejší nález.**
- Navyše **377 ľudí počulo odhad obnovy, ktorý už uplynul.**

**Kto vlastní opravu:**

| Problém | My (účet Voltika) | Produktový tím | Voltika |
|---|---|---|---|
| OMS incident → zloženie | retry, hlásenie aj bez OMS, alert | | príčina incidentu, stabilita OMS |
| Nebezpečné hovory bez dispečera | urgentné hlásenie + pokyny + 112 | | limit frontu, nočné obsadenie |
| Adresy | aliasy častí obcí a ulíc | vyhľadávanie bez medzier, nevracať odmietnutú adresu | chýbajúce adresy v registri |
| Staré ETA | nečítať ETA v minulosti | | aktualizácia ETA v OMS |
| SMS | napojenie vo flowe | SMS funkcia | súhlas s posielaním toho, čo už hovorí bot |
| Metrika „38 %“ | | dashboard podľa výsledku hovoru | |

## 3. Odpoveď klientke

> **Predmet:** Nedeľná noc: čo sa stalo a čo s tým robíme
>
> Dobrý deň, pani Hudecová,
>
> ďakujem za priamu spätnú väzbu. Prešli sme všetkých 11 400 hovorov.
>
> 38 % je podiel hovorov, ktoré ukončil bot. Sedem z desiatich sú bežné rozlúčky po oznámení poruchy. Bot vybavil 80 % hovorov. Reálne zlyhalo **1 368 hovorov (12 %)** a v nich naozaj len zložil:
>
> - **684:** medzi 21:40 a 22:30 váš systém výpadkov odpovedal pomaly alebo vôbec. Prosím o kontakt na vaše IT, potrebujeme spolu zistiť, čo sa o 21:40 zmenilo. Že bot nemal náhradný postup, je naša chyba.
> - **456:** bot nerozpoznal adresu.
> - **228** hlásení nebezpečnej situácie sa nedostalo k dispečerovi, front bol plný. Toto považujeme za najvážnejšie.
>
> Do stredy upravíme a otestujeme postup: pri výpadku systému aj pri plnom fronte bot vždy prijme hlásenie a pri nebezpečenstve dá bezpečnostné pokyny vrátane 112.
>
> K vypnutiu: traja noční operátori vybavia okolo 45 hovorov za hodinu, v špičke ich prišlo 2 600.
>
> SMS chceme, ale len s aktuálnym odhadom, lebo 377 ľudí počulo čas, ktorý už uplynul. Navrhneme aj SMS pre ľudí, ktorým bot nepomohol. Termín potvrdíme do piatka.
>
> Môžeme sa zajtra na 30 minút spojiť?
>
> S pozdravom

## 4. Čo ďalej

1. **My, do stredy: bot nikdy nekončí naprázdno.** Keď OMS zlyhá, 1× retry a potom aj tak hlásenie (adresa je overená). Keď zlyhá prepojenie pri nebezpečenstve, urgentné hlásenie pre dispečing, pokyny držať sa ďalej a 112 pri ohrození života. Keď sa nenájde adresa, hlásenie s obcou a pôvodným textom na ručné spracovanie. **Pokrýva to takmer všetkých 1 368 zlyhaní.** Pri 60 zlyhaných `create_ticket` treba hlásenie zaradiť do fronty a dozaložiť. K tomu alert na chybovosť OMS (incident by sme videli o 21:45, nie ráno).
2. **My + produkt: adresy.** Vyhľadávanie bez medzier na nočných dátach rieši **291 zo 456** neúspešných adries, 593 hovorov by prešlo na prvý pokus a nevzniká žiadna zlá zhoda. Nečítať ETA, ktoré už uplynulo (377).
3. **Voltika:** príčina incidentu o 21:40 a 22:30, limit frontu dispečingu (10) a overflow, chýbajúce adresy v registri (~165). **Otázka:** vie OMS odpovedať pre obec alebo ulicu? Výpadky sú po oblastiach, takže pri nejasnej adrese by bot vedel povedať stav oblasti (príloha B).
4. **SMS od budúceho týždňa:** je to malá zmena. SMS pošle presne to, čo už povedal bot, takže od Voltiky stačí jeden súhlas, žiadne nové texty. Dátum nesľúbim, kým s produktom neoverím SMS bránu. Navrhnem pilot: ETA SMS len s budúcim časom a následnú SMS pre ~1 530 ľudí, ktorým bot nepomohol („volali ste nám, hlásenie evidujeme / pošlite adresu cez odkaz“). Odhad ~80 € za noc pri 0,05 €/SMS.
5. **Vypnúť bota? Nie.** 3 operátori × 15 hovorov/h (4 min) = **45 hovorov/h**, v špičke prišlo **2 600/h**. Za noc by ľudia zvládli ~270 z 11 400 hovorov, bot vybavil 9 120. Bez bota by ~97 % volajúcich počulo obsadzovací tón, aj tí so spadnutým drôtom. Treba opraviť 12 % zlyhaní, nie vypnúť 80 % úspechov.

---

## Príloha A: incident 21:40 – 22:30

Metriky OMS od Voltiky položené vedľa našich hovorov, po 5 minútach:

| | pred (21:15–21:35) | **21:40–22:25** | po (22:35–22:50) |
|---|---|---|---|
| Dopyty na OMS / 5 min | ~178 | **~175, bez zmeny** | ~172 |
| Medián odpovede | 1,0 s | **~6 s** | 1,0 s |
| Chybovosť | ~1 % | **~30 %** | ~1 % |
| API_ERROR / 5 min | 1–3 | **50–72** | 0–3 |
| Zložili počas čakania / 5 min | 12–19 | **21–44** | 9–17 |

- **Nie je to preťaženie.** Záťaž bola pred, počas aj po rovnaká. Zlyhanie začalo aj skončilo skokom (21:40 a 22:30), čo ukazuje na zmenu vo vnútri OMS: nasadenie, prepnutie, zámok v databáze alebo hromadný import poruchových dát.
- **Sme jediný meraný klient.** OMS zaznamenal 9 451 dopytov, presne toľko `get_outage` poslal bot. Metriky nehovoria nič o tom, ako OMS fungoval pre iné systémy Voltiky.
- **Náš podiel:** timeout 8 s (p95 = 8 000 ms je náš strop), žiadny retry, žiadny náhradný postup. Pritom ~70 % dopytov v okne prešlo, len pomaly (medián 4,7 s), takže jeden retry by zachránil odhadom ~400 hovorov.
- V tom istom okne zlyhalo 54 zo 60 `create_ticket`. Naša služba teda zrejme tiež závisí od OMS. Overíme interne.
- **Otázky na IT Voltiky:** čo sa zmenilo o 21:40 a o 22:30? Bol OMS pomalý aj pre dispečing a mapu výpadkov? Zapisuje `create_ticket` do OMS?

## Príloha B: čo by ktorá oprava zachránila (merané na nedeľnej noci)

| Oprava | Vlastník | Hovory / ľudia |
|---|---|---|
| Hlásenie aj pri zlyhaní OMS | my | 684 hovorov |
| 1× retry OMS | my | ~400 hovorov (odhad z 70 % úspešnosti v okne) |
| Urgentné hlásenie + pokyny pri neúspešnom prepojení | my | 228 nebezpečných situácií |
| Vyhľadávanie adresy bez medzier | my + produkt | 291 zo 456, 593 rýchlejšie, 0 zlých zhôd |
| Hlásenie s obcou pri nenájdenej adrese | my | zvyšných 165 |
| Alert na chybovosť OMS | my | odhalenie o 21:45 namiesto rána |
| Nečítať ETA v minulosti | my + Voltika | 377 hovorov |
| Následná SMS | produkt + Voltika | ~1 530 ľudí, ~80 €/noc |

**Adresy.** ASR delí slová („krá tka“, „se nec“, „tridsa ťštyri“). Skúšali sme dve verzie. Spájanie susedných slov (pôvodná veta, potom 1+2, 2+3, …, max. 12 pokusov) vyriešilo 171 zo 456 za 11 ms na vetu. Zmazanie všetkých medzier a hľadanie ulice, čísla (aj slovom) a obce ako podreťazcov vyriešilo **291 zo 456 na jeden pokus za 0,45 ms**. Na 9 451 hovoroch so známou správnou adresou nevrátilo ani jednu zlú adresu. Bot adresu aj tak zopakuje na potvrdenie. Čas výpočtu nie je problém. Volajúci strácajú čas tým, že adresu opakujú (~10 s na pokus). Zvyšných 165 hovorov sú zrozumiteľné adresy, ktoré v našom registri chýbajú, pravdepodobne medzera v registri Voltiky. Overenie vyžaduje plný register.

**Odpoveď podľa oblasti.** Výpadky v sieti sú po oblastiach (trafostanica, vedenie), nie po domoch. Keby OMS vedel odpovedať pre obec alebo ulicu, bot by pri nejasnej adrese povedal „vo vašej časti obce evidujeme poruchu, odhad je…“. **Testovacie dáta to nepotvrdzujú:** v každej obci je 500+ rôznych porúch so všetkými odhadmi od 23:00 do 04:00 a ~30 % adries poruchu nemá. Preto to navrhujeme ako otázku pre Voltiku, nie ako hotové riešenie.

**SMS.** Organizačné SMS idú cez SMS bránu s odosielateľom „Voltika“. Číslo volajúceho má telefónny systém, v našich dátach je len hash. Dosah po ľuďoch: 5 639 s poruchou a odhadom, 499 s výpadkom OMS, 310 s nerozpoznanou adresou, 148 s nebezpečnou situáciou bez dispečera, 620 zložilo skôr. Cena 0,05 €/SMS je predpoklad, treba overiť u poskytovateľa.
