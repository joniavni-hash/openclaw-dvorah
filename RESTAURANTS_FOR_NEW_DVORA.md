# RESTAURANTS.md

מטרת הקובץ: להפוך חיפוש והזמנת מסעדות לתהליך מהיר, יעיל וזול.
עודכן: 2026-04-11 | סה"כ: 200 מסעדות (175 Ontopo + 25 Tabit)

## כלל עבודה
במסעדות בתל אביב והסביבה:
1. קודם לבדוק אם המסעדה יושבת על **Ontopo**
2. אם לא, לבדוק **Tabit**
3. דפדפן רק אם אין דרך אחרת

## סטטוסי זמינות
- `seat` = יש שולחן לאישור מיידי
- `callback` = בקשה לצוות האירוח
- `disabled` = אין מקום

## URL Patterns
- **Ontopo**: `https://ontopo.com/en/il/page/{slug}` (slug = text or numeric ID)
- **Ontopo Hebrew**: `https://ontopo.com/he/il/page/{slug}`
- **Ontopo Menu**: `https://ontopo.co.il/en/{slug}/menu`
- **Tabit (option 1)**: `https://tgm-rsv.tabit.cloud/#!/{orgId}/booking/search`
- **Tabit (option 2)**: `https://tabitisrael.co.il/online-reservations/create-reservation?step=search&orgId={orgId}`
- **Browse by city**: `https://ontopo.com/en/il/{city}` (tel-aviv, jerusalem, haifa, herzliya, raanana, ramat-gan, netanya, ashdod, beer-sheva, eilat, rehovot, rishon-lezion, petah-tikva, kfar-saba, hod-hasharon)
- **Browse by tag**: `https://ontopo.com/en/il/{city}/tags/{tag}` (tasting_menu, romantic, kosher, israeli, italian, asian, seafood, steak)

## API Pattern ל-Ontopo
POST `https://ontopo.com/api/availability_search`

Payload pattern:
```json
{
  "slug": "<restaurant-slug>",
  "locale": "he",
  "criteria": {
    "date": "YYYYMMDD",
    "time": "HHMM",
    "size": "<party-size>"
  },
  "data": {
    "analytics": {
      "market_id": "",
      "venue_id": "<venue-id>",
      "referrer_domain": null,
      "device_id": "<device-id>",
      "platform": "web",
      "distributor_id": "il",
      "origin": "venue_page",
      "sub_origin": null
    }
  }
}
```

Other useful API endpoints:
- `GET /api/venue_search?query={name}` — search by name
- `GET /api/venue_profile?slug={slug}` — get venue details + venue_id

## תשובה למשתמש
להחזיר רק:
- האם יש מקום או לא
- השעות הרלוונטיות
- האם זה אישור מיידי או בקשה לצוות
- בלי לפרט תהליך

---

## תל אביב (59)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| Taizu | `taizu` | Asian-Mediterranean | |
| CAFE TAIZU (Kosher) | `22341758` | Asian-Mediterranean | V |
| Claro | `24489442` | Mediterranean | |
| North Abraxas | `83728647` | Mediterranean | |
| OCD | `88542392` | Tasting Menu | |
| Hasalon | `12618300` | Mediterranean | |
| DVORA | `93609054` | Israeli | V |
| Night Kitchen | `20745964` | Bar & Restaurant | |
| Katzir | `38952955` | Seasonal Israeli | |
| Baba Yaga | `54380456` | European-Mediterranean-Russian | |
| Rendez-vous | `40980635` | French | |
| ASA Izakaya | `99180045` | Japanese | |
| Yaffo Tel Aviv | `34362976` | Mediterranean | |
| Thai House | `thaihouse` | Thai | |
| Thai Street Food | `41859159` | Thai | |
| Ouzeria | `28899692` | Greek-Mediterranean | |
| Onza | `onza` | Turkish-Ottoman | |
| Santa Katarina | `53724621` | Mediterranean | |
| Hotel Montefiore | `65314945` | French-Asian | |
| Montefiore22-A2 | `27962692` | Mediterranean | |
| Imperial | `71673788` | Cocktail Bar | |
| LP | `83229959` | Cocktail Bar & Wine Bar | |
| Cafe Popular | `56055192` | Cafe & Bar | |
| Cafe Europa | `cafeeuropa` | Cafe-Brasserie | |
| Grand Cafe Turkiz | `32409506` | Brasserie | |
| Dizengoff Cafe | `73991020` | Cafe | |
| Cafe Italia | `cafeitalia` | Italian | |
| Barbur Grill & Bar | `30131276` | Mediterranean Grill | |
| Vega Bar | `35175387` | Wine Bar | |
| Jazz Kissa Bar | `72810289` | Jazz Bar | |
| HELENA Wine Bar | `84482361` | Wine Bar & Pintxos | |
| Whiskey Bar & Museum | `54569070` | Whiskey Bar | |
| A la Bar | `52073325` | Bar | |
| Shuffle Bar | `shuffle` | Bar | |
| Deli Vino | `15875485` | Wine Bar & Deli | |
| Flor Wine Shop | `44883169` | Wine Bar | |
| ARIA Restaurant | `18560881` | Mediterranean | |
| Taqueria | `65374258` | Mexican | |
| Ze Sushi | `97169197` | Japanese-Sushi | |
| YAN | `20214686` | Asian-Sushi | |
| Moon Bograshov | `32609329` | Japanese-Sushi | |
| Joya Tel Aviv (Kosher) | `71628036` | Italian | V |
| GRECO KOSHER | `grecokosher` | Mediterranean | V |
| Meatos | `61098150` | Steak | |
| Omnia Brasserie | `34502383` | Steak & Brasserie | |
| Brasserie 18 | `93797570` | Brasserie | |
| POUPEE | `66391500` | French | |
| GABAGOOL Pop Up | `15206084` | Italian-American | |
| RAMA Italian Kitchen & Bar | `54040297` | Italian | |
| animar | `animar` | Mediterranean | |
| animar (Italian evening) | `animaritalian` | Italian | |
| Hudson Lilinblum | `22512632` | American Steakhouse | |
| Hudson Ramat Hahayal | `92184508` | American Steakhouse | |
| Peking Duck House | `23432994` | Chinese | |
| Fifty and One | `67365513` | Mediterranean | |
| Alena (Norman Hotel) | `alena` | Fine Dining | |
| Tasting Room | `tastingroom` | Tasting Menu | |
| Restaurant a (Yuval Ben-Naria) | `83077556` | Asian Street Food | |
| Pastel | `pastel` | Mediterranean | |

## ירושלים (20)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| Machneyuda | `machneyuda` | Mediterranean-Middle Eastern | |
| Pitmaster Jerusalem | `98963887` | Smoked Meat BBQ | V |
| Mona Jerusalem | `46042376` | Mediterranean | |
| Rooftop Jerusalem | `rooftop` | Mediterranean | |
| Veranda Jerusalem | `verandajerusalem` | Mediterranean | |
| CHAKRA | `59594032` | Fish & Seafood | |
| Hamotzi | `50384695` | Israeli | |
| Palomino | `48390724` | Mediterranean | |
| Red Heifer Steakhouse | `24517516` | Steakhouse | |
| Super HaMizrah | `62060742` | Asian | |
| Ramban Hotel Restaurant | `61134791` | Creative Israeli | V |
| Hatzot Jerusalem | `85480469` | Israeli Traditional | V |
| The Grill Room (King David) | `81590357` | Steakhouse | |
| Entrecote Jerusalem | `68638218` | French Steak | |
| Meat Time | `94391109` | Meat | |
| Modern | `33290489` | Creative Jerusalem | |
| Denya Cafe Beit Hakerem | `40536602` | Cafe | |
| Cafe Lyon | `20410429` | French Cafe | |
| Brasserie Ein-Kerem | `brasseriejerusalem` | French Brasserie | |
| Bar Tuv (Beit Shemesh) | `22487621` | Pub | |

## חיפה (14)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| ROLA | `34883468` | Arab-Levantine | |
| Najma | `39737206` | Mediterranean | |
| Nirvana | `nirvana` | Mediterranean | |
| Raseef 33 | `93074107` | Mediterranean Fusion | |
| Ruben Neve Shaanan | `40858914` | American Steakhouse | |
| Ruben Big Krayot | `96548878` | American Steakhouse | |
| Sinta Bar | `88557245` | Bistro | |
| Talpiot | `28407902` | Hamara-Casual | |
| Pub Morgan | `98102567` | Pub | |
| Del-mar | `20180981` | Fish & Seafood | |
| Reef Cafe | `93250189` | Dairy Cafe | |
| Strudel | `59892064` | Mediterranean-Italian | |
| Tatami | `55965290` | Asian Fusion-Sushi | |
| Shwarma Bili | `52399450` | Shawarma | |

## הרצליה (13)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| Sunset Kitchen (Daniel Hotel) | `47003649` | Dairy Chef | V |
| Calata 15 | `calata15` | Italian | |
| Herbert Samuel (Ritz Carlton) | `39102664` | Chef Restaurant | V |
| Nono | `91751874` | Italian | |
| Zozobra | `93323870` | Mediterranean | |
| Gazebbo | `gazebbo` | Beach Restaurant | |
| Nafis | `nafishertz` | Bar-Restaurant | |
| Venice Beach Bar | `61231325` | Beach Bar | |
| Cafe Tiran | `13283953` | Cafe | |
| Yam Bar | `15296344` | Bar | |
| Al Hamayim (Kosher) | `62402502` | Mediterranean | V |
| Cafe Toscana | `28865745` | Italian Cafe | |
| Bangkok Kitchen | `81805588` | Thai | |

## רמת גן (11)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| River Sushi | `50675914` | Japanese-Sushi | |
| Pizza Karina | `35199130` | Pizza | |
| PLAZA | `53924943` | Mediterranean | |
| Otoro Handroll Bar | `88640968` | Japanese | |
| frug&co | `66519014` | Cafe-Restaurant | |
| Shula BaHatzer | `shulaba` | Israeli | |
| Miss V | `43040634` | Vegan Asian | |
| Sai Sushi Bar | `38182106` | Japanese-Sushi | |
| Neighbors Ramat Chen | `68314587` | Mediterranean | |
| Cafe Lugano | `19516853` | Cafe | |
| Fresh the Market Ayalon | `58172775` | Fresh Market | |

## רעננה (3)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| Felicita | `22063899` | Italian | |
| Brasserie Kazan | `kazan` | French Brasserie | |
| HaVeDa | `11217820` | Mediterranean | |

## ראשון לציון (5)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| Burattino | `45480858` | Italian Chef | |
| Tampopo | `95357961` | Japanese-Sushi | |
| Vivino | `25787144` | Mediterranean | |
| Belago | `25871046` | Mediterranean | |
| Se Tu Pizza & Bar | `15511330` | Italian-Pizza | |

## רחובות (6)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| La La | `59819678` | Wine Bar | V |
| River Rehovot | `24173244` | Noodles & Sushi | |
| Fabrica | `fabrica` | Mediterranean | |
| La Morse | `70185226` | Mediterranean | |
| Dublin Rehovot | `75361998` | Pub | |
| Hamburg | `70202128` | Burgers | |

## פתח תקווה (3)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| Patrick's Rooftop | `71087242` | Bar-Restaurant | V |
| MARGAUX | `64872830` | French Brasserie | V |
| Lechem Basar | `30722100` | Meat | V |

## נתניה (5)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| Rhythm Social and Front | `42972265` | Bar-Restaurant | |
| Jacko | `84002699` | Mediterranean | |
| Rumor 22 Poleg | `rumor22poleg` | Mediterranean | |
| Murphy's Natanya | `24924737` | Pub | |
| Furman's Bar | `55214678` | Bar | |

## באר שבע (3)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| Goomba | `44232862` | Asian | |
| Kepasa | `32321286` | Mediterranean | |
| BASTORY | `63121533` | Bar-Restaurant | |

## כפר סבא (2)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| Jem's Beer Factory | `64450747` | Pub & Beer | |
| Japanika | `17460292` | Japanese-Sushi | |

## אילת (2)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| Israelit | `14023625` | Mediterranean | |
| Hamifratz | `29583986` | Israeli | |

## אשדוד (4)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| OIA Kosher Greek | `38460436` | Greek | V |
| Farino Pizza | `38116326` | Pizza | |
| Trump Kosher | `95337026` | Mediterranean | V |
| Idi Fish Restaurant | `89276009` | Fish & Seafood | |

## אשקלון (1)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| Brasserie Marine | `55280391` | French Brasserie | |

## צפון (13)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| Limousine (Ramat Yishai) | `limousine` | Steakhouse | |
| Pitmaster Alonim | `51951438` | Smoked Meat BBQ | V |
| Bat Harim (Zikhron Ya'akov) | `batharim` | Deli & Wine Bar | |
| Wine Bar (Pardes Hanna) | `77070660` | Wine Bar | |
| Fiori Italian House (Pardes Hanna) | `39676585` | Italian | |
| Iron Restaurant (Pardes Hanna) | `31665860` | Meat | |
| Travel Hotel (Gesher Haziv) | `24970918` | Hotel Restaurant | |
| Chateau Golan (Eliad) | `22699582` | Winery | |
| Berkat Ram (Majdal al-Shams) | `34709230` | Local Golan | |
| Sushi Sho Fi (Daliyat al-Karmel) | `58816226` | Japanese-Sushi | |
| House Restaurant (Ein Hawd) | `24343425` | Arabic Home Cooking | |
| Cafe LaLush | `cafelalush` | Brasserie | |
| Rutenberg (Gesher) | `rutenberg` | Mediterranean | |

## דרום (2)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| Rosemary (Mitzpe Ramon) | `73618102` | Mediterranean | |
| Japan Japan (Mitzpe Ramon) | `32462840` | Japanese-Asian | V |

## שאר הארץ (9)

| שם | Slug | סוג | כשר |
|----|------|------|------|
| Bella Restaurant (Beit She'arim) | `24809579` | Italian-Mediterranean | |
| Le Restaurant (Airport City) | `27142318` | French | |
| Landwer Cafe (Airport City) | `82844212` | Cafe | |
| Landwer Cafe (Kadima Zoran) | `24471413` | Cafe | |
| Bueno Kosher Italian (Yehud-Monosson) | `47306494` | Italian | V |
| Kan Kai Sushi Wok Bar (Rosh Haayin) | `14515071` | Japanese | |
| Abdalla Grill (Or Yehuda) | `32737064` | Meat Grill | |
| Vinny Wine Bar (Givatayim) | `19284048` | Wine Bar | |
| Luchana Gea | `78817318` | Mediterranean | |

---

## Tabit (25 known)

Tabit has no public directory. IDs are 24-char hex strings (orgId).
Booking URL options:
- `https://tgm-rsv.tabit.cloud/#!/{id}/booking/search`
- `https://tabitisrael.co.il/online-reservations/create-reservation?step=search&orgId={id}`
The Tabit app (iOS/Android) has built-in search by area.

### תל אביב

| שם | Tabit orgId | עיר |
|----|-------------|------|
| Mashya (משייה) | `59f6e8a0dd87c02200c8488c` | תל אביב |
| Turkiz Restaurant | `609928ba4e68f9c4a94eaa25` | תל אביב |
| טוטו | `612c94440d569b1367ca96a9` | תל אביב |
| Grand Cafe (גרנד קפה) | `5e2076c84ecb9dc7409db5ad` | תל אביב |
| Moshik& | `666fdd6215d9f2a3682e49ee` | תל אביב |
| האחים | `5adc4303e98e0717008ce965` | תל אביב |
| Aka | `62de6bc0d2b0b203510fd3de` | תל אביב |
| TATAMI Tel Aviv | tabitisrael.co.il/site/tatami-תל-אביב | תל אביב |
| מחנה אסאדה | tabitisrael.co.il/site/מחנה-אסאדה-תל-אביב | תל אביב |
| Bo'u (בואו) | `695babbebbf78e1114c7f6a3` | תל אביב |
| Ad HaEtzem Express | `5b2a05572ee2b91700125eb6` | תל אביב |

### ירושלים

| שם | Tabit orgId | עיר |
|----|-------------|------|
| The Palace Restaurant | `62d7bd33fdaa58d7011905c6` | ירושלים |
| King's Court Restaurant | `62d7bdf03d54e4515b9e24bb` | ירושלים |
| Cafe Rimon (מדרחוב בן יהודה) | `5f72dd14f2e56cd68bc5bb63` | ירושלים |
| Margo Wine Bar & Restaurant | `62e24bb6b2c3576635d1f354` | ירושלים |

### הרצליה ושרון

| שם | Tabit orgId | עיר |
|----|-------------|------|
| Yam 7 (ים 7) | `6022527f7eccba86572ea7e9` | הרצליה |
| Johnny Wine Bar (ג'וני בר יין) | `6405b1188f7ca96c8221f5b9` | הרצליה |
| Sushi Room Hills | `5e1dc42f632bd14093f4125e` | הרצליה |
| Ginza Sushi Bar | `5c3d9c7ba265d81ebfe38da0` | הרצליה פיתוח |
| רביבה וסיליה | `57b010e4cb82f61e009fe53a` | רמת השרון |
| Nooch | `590b1a62140f622200805d2a` | רמת השרון |
| Giraffe | `60fd7b148393393511caaedf` | גלילות |
| נונו הוד השרון | `582ae49284574a1f00fc76e4` | הוד השרון |

### שאר הארץ

| שם | Tabit orgId | עיר |
|----|-------------|------|
| Mood Restaurant | `60a36e8f9234fdac785de5c4` | אילת |
| Dolce (דולצ'ה) | `5eb000d40c7f98e444e32a16` | רעננה |
| Rooftop Sky Bar | `5cb882ec27fb837df427158e` | רעננה |
| או לה לה | `6135de3013c3c745fae2acc5` | באר שבע |
| Jem's Rehovot | `5caf30d0423d6bea51a86145` | רחובות |
| יקב טוליפ Le Bar | `61c07b4244fd3fe1e84014b3` | קרית טבעון |
| סעידה בפארק | `5c87a722938e83264a853d05` | חולון |
| Lighthouse 5th FLOOR | `5de3cc47f40017e0d061aec9` | תל אביב |
| Tabit Dine Smart | `59ad40607f99812200344be2` | רשפון |

---

## איך להוסיף מסעדה חדשה

1. חפש את השם ב-`https://ontopo.com/api/venue_search?query={name}`
2. קח את ה-slug מה-URL של דף המסעדה
3. הוסף שורה לטבלה של העיר הרלוונטית
4. אם זה Tabit, חפש `"tgm-rsv.tabit.cloud" {restaurant_name}` בגוגל
