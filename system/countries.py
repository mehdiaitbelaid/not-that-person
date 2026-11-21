"""Country names, ISO codes and nationalities mapped to one name (principle 6:
codes and nationalities are countries; territories count as their own country)."""
import re

from names import fold

# name | ISO2 | ISO3 | other forms (nationality adjectives, short names)
TABLE = """
Afghanistan|AF|AFG|afghan
Albania|AL|ALB|albanian
Algeria|DZ|DZA|algerian
Andorra|AD|AND|andorran
Angola|AO|AGO|angolan
Argentina|AR|ARG|argentine,argentinian
Armenia|AM|ARM|armenian
Australia|AU|AUS|australian
Austria|AT|AUT|austrian
Azerbaijan|AZ|AZE|azerbaijani,azeri
Bahamas|BS|BHS|bahamian,the bahamas
Bahrain|BH|BHR|bahraini
Bangladesh|BD|BGD|bangladeshi
Barbados|BB|BRB|barbadian
Belarus|BY|BLR|belarusian
Belgium|BE|BEL|belgian
Belize|BZ|BLZ|belizean
Benin|BJ|BEN|beninese
Bermuda|BM|BMU|bermudian
Bolivia|BO|BOL|bolivian
Bosnia and Herzegovina|BA|BIH|bosnian,bosnia,bosnia herzegovina
Botswana|BW|BWA|botswanan,motswana
Brazil|BR|BRA|brazilian
British Virgin Islands|VG|VGB|virgin islands british
Brunei|BN|BRN|bruneian
Bulgaria|BG|BGR|bulgarian
Burkina Faso|BF|BFA|burkinabe
Cambodia|KH|KHM|cambodian
Cameroon|CM|CMR|cameroonian
Canada|CA|CAN|canadian
Cayman Islands|KY|CYM|caymanian
Chad|TD|TCD|chadian
Chile|CL|CHL|chilean
China|CN|CHN|chinese,peoples republic of china,prc
Colombia|CO|COL|colombian
Congo|CG|COG|congolese,republic of the congo
Democratic Republic of the Congo|CD|COD|dr congo,drc,congo kinshasa
Costa Rica|CR|CRI|costa rican
Cote d'Ivoire|CI|CIV|ivorian,ivory coast,cote divoire
Croatia|HR|HRV|croatian
Cuba|CU|CUB|cuban
Cyprus|CY|CYP|cypriot
Czech Republic|CZ|CZE|czech,czechia
Denmark|DK|DNK|danish,dane
Dominican Republic|DO|DOM|dominican
Ecuador|EC|ECU|ecuadorian,ecuadorean
Egypt|EG|EGY|egyptian
El Salvador|SV|SLV|salvadoran
Eritrea|ER|ERI|eritrean
Estonia|EE|EST|estonian
Ethiopia|ET|ETH|ethiopian
Finland|FI|FIN|finnish
France|FR|FRA|french
Gabon|GA|GAB|gabonese
Gambia|GM|GMB|gambian,the gambia
Georgia|GE|GEO|georgian
Germany|DE|DEU|german
Ghana|GH|GHA|ghanaian
Gibraltar|GI|GIB|gibraltarian
Greece|GR|GRC|greek
Guatemala|GT|GTM|guatemalan
Guernsey|GG|GGY|
Guinea|GN|GIN|guinean
Guyana|GY|GUY|guyanese
Haiti|HT|HTI|haitian
Honduras|HN|HND|honduran
Hong Kong|HK|HKG|hong kong sar,hong kong special administrative region of china
Hungary|HU|HUN|hungarian
Iceland|IS|ISL|icelandic
India|IN|IND|indian
Indonesia|ID|IDN|indonesian
Iran|IR|IRN|iranian,islamic republic of iran
Iraq|IQ|IRQ|iraqi
Ireland|IE|IRL|irish,republic of ireland
Isle of Man|IM|IMN|manx
Israel|IL|ISR|israeli
Italy|IT|ITA|italian
Jamaica|JM|JAM|jamaican
Japan|JP|JPN|japanese
Jersey|JE|JEY|
Jordan|JO|JOR|jordanian
Kazakhstan|KZ|KAZ|kazakh,kazakhstani
Kenya|KE|KEN|kenyan
Kosovo|XK|XKX|kosovar,kosovan
Kuwait|KW|KWT|kuwaiti
Kyrgyzstan|KG|KGZ|kyrgyz
Laos|LA|LAO|lao,laotian
Latvia|LV|LVA|latvian
Lebanon|LB|LBN|lebanese
Liberia|LR|LBR|liberian
Libya|LY|LBY|libyan
Liechtenstein|LI|LIE|
Lithuania|LT|LTU|lithuanian
Luxembourg|LU|LUX|luxembourgish,luxembourger
Macao|MO|MAC|macau,macanese,macao special administrative region of china
Madagascar|MG|MDG|malagasy
Malawi|MW|MWI|malawian
Malaysia|MY|MYS|malaysian
Maldives|MV|MDV|maldivian
Mali|ML|MLI|malian
Malta|MT|MLT|maltese
Mauritania|MR|MRT|mauritanian
Mauritius|MU|MUS|mauritian
Mexico|MX|MEX|mexican
Moldova|MD|MDA|moldovan,republic of moldova
Monaco|MC|MCO|monegasque
Mongolia|MN|MNG|mongolian
Montenegro|ME|MNE|montenegrin
Morocco|MA|MAR|moroccan
Mozambique|MZ|MOZ|mozambican
Myanmar|MM|MMR|burmese,burma
Namibia|NA|NAM|namibian
Nepal|NP|NPL|nepalese,nepali
Netherlands|NL|NLD|dutch,holland,the netherlands
New Zealand|NZ|NZL|new zealander,kiwi
Nicaragua|NI|NIC|nicaraguan
Niger|NE|NER|nigerien
Nigeria|NG|NGA|nigerian
North Korea|KP|PRK|north korean,democratic peoples republic of korea,dprk
North Macedonia|MK|MKD|macedonian,macedonia
Northern Mariana Islands|MP|MNP|
Norway|NO|NOR|norwegian
Oman|OM|OMN|omani
Pakistan|PK|PAK|pakistani
Palestine|PS|PSE|palestinian,palestina,state of palestine,palestinian territories
Panama|PA|PAN|panamanian
Papua New Guinea|PG|PNG|
Paraguay|PY|PRY|paraguayan
Peru|PE|PER|peruvian
Philippines|PH|PHL|filipino,philippine
Poland|PL|POL|polish,pole
Portugal|PT|PRT|portuguese
Puerto Rico|PR|PRI|puerto rican
Qatar|QA|QAT|qatari
Romania|RO|ROU|romanian
Russia|RU|RUS|russian,russian federation
Rwanda|RW|RWA|rwandan
Saudi Arabia|SA|SAU|saudi,saudi arabian
Senegal|SN|SEN|senegalese
Serbia|RS|SRB|serbian
Sierra Leone|SL|SLE|sierra leonean
Singapore|SG|SGP|singaporean
Slovakia|SK|SVK|slovak,slovakian
Slovenia|SI|SVN|slovenian,slovene
Somalia|SO|SOM|somali
South Africa|ZA|ZAF|south african
South Korea|KR|KOR|south korean,korea,republic of korea
South Sudan|SS|SSD|south sudanese
Spain|ES|ESP|spanish
Sri Lanka|LK|LKA|sri lankan
Sudan|SD|SDN|sudanese
Sweden|SE|SWE|swedish,swede
Switzerland|CH|CHE|swiss
Syria|SY|SYR|syrian,syrian arab republic
Taiwan|TW|TWN|taiwanese
Tajikistan|TJ|TJK|tajik
Tanzania|TZ|TZA|tanzanian
Thailand|TH|THA|thai
Togo|TG|TGO|togolese
Trinidad and Tobago|TT|TTO|trinidadian,tobagonian
Tunisia|TN|TUN|tunisian
Turkey|TR|TUR|turkish,turkiye
Turkmenistan|TM|TKM|turkmen
Uganda|UG|UGA|ugandan
Ukraine|UA|UKR|ukrainian
United Arab Emirates|AE|ARE|emirati,uae
United Kingdom|GB|GBR|british,uk,great britain,britain,england,scotland,wales,northern ireland,english,scottish,welsh
United States|US|USA|american,united states of america,us,u s,u s a
Uruguay|UY|URY|uruguayan
Uzbekistan|UZ|UZB|uzbek
Venezuela|VE|VEN|venezuelan
Vietnam|VN|VNM|vietnamese,viet nam
Yemen|YE|YEM|yemeni
Zambia|ZM|ZMB|zambian
Zimbabwe|ZW|ZWE|zimbabwean
Aland Islands|AX|ALA|
American Samoa|AS|ASM|
Anguilla|AI|AIA|
Antarctica|AQ|ATA|
Antigua and Barbuda|AG|ATG|antiguan
Aruba|AW|ABW|
Bhutan|BT|BTN|bhutanese
Bonaire, Sint Eustatius and Saba|BQ|BES|bonaire
Bouvet Island|BV|BVT|
British Indian Ocean Territory|IO|IOT|
Burundi|BI|BDI|burundian
Cabo Verde|CV|CPV|cape verde,cape verdean
Central African Republic|CF|CAF|central african
Christmas Island|CX|CXR|
Cocos (Keeling) Islands|CC|CCK|cocos islands
Comoros|KM|COM|comoran
Cook Islands|CK|COK|
Curacao|CW|CUW|
Djibouti|DJ|DJI|djiboutian
Dominica|DM|DMA|
Equatorial Guinea|GQ|GNQ|equatoguinean
Eswatini|SZ|SWZ|swaziland,swazi
Falkland Islands|FK|FLK|falklands
Faroe Islands|FO|FRO|faroese
Fiji|FJ|FJI|fijian
French Guiana|GF|GUF|
French Polynesia|PF|PYF|
French Southern Territories|TF|ATF|
Greenland|GL|GRL|greenlandic
Grenada|GD|GRD|grenadian
Guadeloupe|GP|GLP|
Guam|GU|GUM|
Guinea-Bissau|GW|GNB|guinea bissau
Heard Island and McDonald Islands|HM|HMD|
Holy See|VA|VAT|vatican,vatican city
Kiribati|KI|KIR|
Lesotho|LS|LSO|basotho
Marshall Islands|MH|MHL|marshallese
Martinique|MQ|MTQ|
Mayotte|YT|MYT|
Micronesia|FM|FSM|micronesian,federated states of micronesia
Montserrat|MS|MSR|
Nauru|NR|NRU|nauruan
New Caledonia|NC|NCL|
Niue|NU|NIU|
Norfolk Island|NF|NFK|
Palau|PW|PLW|palauan
Pitcairn|PN|PCN|
Reunion|RE|REU|
Saint Barthelemy|BL|BLM|
Saint Helena|SH|SHN|
Saint Kitts and Nevis|KN|KNA|
Saint Lucia|LC|LCA|saint lucian
Saint Martin|MF|MAF|
Saint Pierre and Miquelon|PM|SPM|
Saint Vincent and the Grenadines|VC|VCT|
Samoa|WS|WSM|samoan
San Marino|SM|SMR|sammarinese
Sao Tome and Principe|ST|STP|
Seychelles|SC|SYC|seychellois
Sint Maarten|SX|SXM|
Solomon Islands|SB|SLB|
South Georgia and the South Sandwich Islands|GS|SGS|
Suriname|SR|SUR|surinamese
Svalbard and Jan Mayen|SJ|SJM|
Timor-Leste|TL|TLS|east timor,timorese
Tokelau|TK|TKL|
Tonga|TO|TON|tongan
Turks and Caicos Islands|TC|TCA|
Tuvalu|TV|TUV|tuvaluan
United States Minor Outlying Islands|UM|UMI|
US Virgin Islands|VI|VIR|united states virgin islands,virgin islands us
Vanuatu|VU|VUT|ni vanuatu
Wallis and Futuna|WF|WLF|
Western Sahara|EH|ESH|sahrawi
"""


# Not countries (principle 5 names International and Europe; the rest are the same kind)
REGIONS = {"international", "europe", "global", "worldwide", "world", "africa", "asia",
           "middle east", "latin america", "south america", "north america", "americas",
           "caribbean", "oceania", "european union", "eu", "balkans", "scandinavia",
           "gulf", "west africa", "east africa", "southeast asia", "central asia",
           "unknown", "not known", "n/a", "na", "none", "other", "various", "multiple"}

ALIAS = {}
CODES = {}
for line in TABLE.strip().splitlines():
    name, a2, a3, rest = (line.split("|") + [""] * 4)[:4]
    for form in [name] + [x for x in rest.split(",") if x]:
        ALIAS[re.sub(r"[^a-z ]", "", fold(form)).strip()] = name
    CODES[a2] = name
    CODES[a3] = name


def key(s):
    s = re.sub(r"[^a-z ]", " ", fold(s).replace("'", ""))
    return re.sub(r"\s+", " ", s).strip()


def norm(value):
    """One place string to a country name, or None when it names no country."""
    if not value:
        return None
    v = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", str(value)).strip()
    if not v:
        return None
    raw = v.strip(" .,")
    # a whole field that is only a code is a country in any letter case ("fr")
    if len(raw) in (2, 3) and raw.isalpha() and raw.upper() in CODES:
        return CODES[raw.upper()]
    k = key(raw)
    if not k or k in REGIONS:
        return None
    if k in ALIAS:
        return ALIAS[k]
    if k.startswith("the ") and k[4:] in ALIAS:
        return ALIAS[k[4:]]
    return None


def unread(value):
    """True when a place string is given but names no country we know. Such a
    place stays unknown, and unknown blocks a location clearance."""
    if not value:
        return False
    v = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", str(value)).strip()
    if not key(v):
        return False
    return key(v) not in REGIONS and norm(v) is None


def last_part(value):
    """Addresses and places: the country is the last comma part."""
    v = re.sub(r"\[[^\]]*\]", " ", str(value or "")).strip().strip(",")
    if not v:
        return None
    return v.split(",")[-1].strip()


def mentioned(text):
    """Countries named in free text, by name or nationality adjective."""
    found = set()
    k = " " + key(text) + " "
    for alias, name in ALIAS.items():
        if len(alias) < 3 or alias in ("us", "uk", "eu"):
            continue
        if " " + alias + " " in k:
            found.add(name)
    # bare uppercase codes such as US or UK inside a sentence
    for m in re.finditer(r"\b(US|USA|UK|UAE)\b", text or ""):
        found.add({"US": "United States", "USA": "United States",
                   "UK": "United Kingdom", "UAE": "United Arab Emirates"}[m.group(1)])
    # a longer name contains a shorter one (South Sudan holds Sudan, Niger in Nigeria is
    # already separated by spaces); drop names wholly inside a longer found alias
    out = set(found)
    for a in found:
        for b in found:
            if a != b and key(a) in key(b) and (" " + key(b) + " ") in k:
                out.discard(a)
    return out


PLACE_CODE = re.compile(r"(?:\b(?:in|from|to|and|or|at|of|country|nationality|residence)\s*:?\s+|,\s*|\(\s*)([A-Z]{2,3})\b(?![-\w])")


def code_in_place(place):
    """A place written as an ISO alpha 2 or alpha 3 code."""
    v = (place or "").strip()
    return CODES.get(v) if v.isupper() and len(v) in (2, 3) else None


def codes_in_prose(text):
    """ISO codes in prose, taken only after a place word, a comma or a bracket
    ("lived in France and CD"), never on their own."""
    out = set()
    for m in PLACE_CODE.finditer(text or ""):
        c = CODES.get(m.group(1))
        if c:
            out.add(c)
    return out
