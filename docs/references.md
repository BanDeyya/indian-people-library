# Research references and sensitive-topic guide

A starting point for anyone researching a state or reviewing one. Every fact used in a region file is still cited inside that file's `sources`; this page explains **where to look first** and **how to handle sensitive subjects**. Rules behind it: `AGENTS.md` sections 2 and 3.

---

## 1. Where to look first (priority 1: government and institutional)

| Source | What it is good for |
|---|---|
| [Indian Culture portal](https://indianculture.gov.in/) (Ministry of Culture) | Stories, archives and museum collections on dress, crafts, festivals and communities. Some pages load with JavaScript; if a page comes back empty, look for the same material on a museum or state site. |
| [IGNCA](https://ignca.gov.in/) (Indira Gandhi National Centre for the Arts) | Research pages on regional textiles and traditions, e.g. [Textiles of Mizoram](https://ignca.gov.in/?p=50872), which lists cloths with honour and ceremonial meanings per community. |
| [Anthropological Survey of India](https://ansi.gov.in/about?lang=en) (Ministry of Culture) | Field research on India's communities, their social and cultural life. |
| [GI registry search](https://search.ipindia.gov.in/GIRPublic/Application/Details/4) (Intellectual Property India) | Registered geographical indications: which handloom and craft (e.g. a saree weave) truly belongs to which place. |
| Bharatiya Vastra evam Shilpa Kosh (Ministry of Textiles knowledge portal) | Repository of Indian textiles and crafts, with a handloom focus ([about](https://en.vikaspedia.in/viewcontent/social-welfare/entrepreneurship/indian-handloom/national-knowledge-portal-of-the-textiles-and-crafts-of-india?lgn=en)). |
| [National Handicrafts and Handlooms Museum](https://www.india.gov.in/official-website-national-handicrafts-and-handlooms-museum) (Crafts Museum, New Delhi) | Museum collections of regional textiles and dress. |
| Census of India (official site) | Religion and language figures per state and district. Until the official tables are linked, region files cite census2011.co.in, which republishes the 2011 figures. |
| State and district government portals | Often the best source for a state's own description of its dress and festivals, e.g. [Culture of Assam](https://assam.gov.in/node/391), [Chirang district attire](https://chirang.assam.gov.in/information-and-services/traditioal-attire). |

**Priority 2:** state museums, Indian university textile and fashion departments, NIFT publications.
**Priority 3:** Indian regional newspapers, community associations, state handloom cooperatives.
**Priority 4:** Wikipedia, only to find the sources above.

**Not used as sources:** foreign travel blogs, Western fashion media, stock-photo sites, Pinterest, SEO "top 10 costumes" pages and copied PDFs (common for this topic), AI-generated articles. Shop pages can confirm a garment exists, nothing more.

---

## 2. Sensitive subjects

### Protected and uncontacted peoples
- The **Sentinelese, Jarawa and Shompen** of the Andaman and Nicobar Islands are excluded from this library entirely.
- Their reserved areas are protected by the [Andaman and Nicobar Islands (Protection of Aboriginal Tribes) Regulation, 1956](https://indiacode.nic.in/bitstream/123456789/19311/1/pat_regualtion_1956.pdf). It allows entry only with a pass and restricts outside land and trade interests.
- A 2012 amendment added a buffer zone of up to 5 km around the Jarawa reserve. Penalties of 3 to 7 years' prison target exploitation, including photography and videography ([Business Standard / PTI](https://business-standard.com/article/pti-stories/govt-makes-exploitation-of-andaman-tribes-jailable-offence-112053100353_1.html)).
- Other Particularly Vulnerable Tribal Groups are not excluded, but need priority 1–2 sources and extra review.

### Marks and items that are earned, not worn
- Some items record an achievement or an office. They must be flagged `restricted: true` and are never given to a generic character.
- Example: older **Konyak Naga facial tattoos** were earned through warfare in the headhunting era, and only a fading generation of elders carries them ([Morung Express](https://morungexpress.com/at-90-one-of-last-tattooed-konyak-headhunters-sees-hope-in-naga-youth)). A young Konyak character must not have them.
- Example: **Mizo, Hmar and Paite honour cloths** were reserved for warriors or for families with outstanding harvests ([IGNCA](https://ignca.gov.in/?p=50872)).

### Community-owned designs
- **Toda embroidery (puthkuli)** from the Nilgiris is a GI-protected handcraft. Toda embroiderers object to copied and machine-made imitations sold under their name ([PARI](https://wagtail.ruralindiaonline.org/en/articles/copying-our-designs-is-not-correct/), [Sahapedia](https://www.sahapedia.org/toda-people-guardians-nilgiris)).
- It is therefore a `restricted` item: never used as decoration, and never generated as if it were real Toda work.
- The same care applies to any GI-registered or community-owned design.

### Contested identity questions
- Do not take sides in disputes over a community's status, for example the Badaga Scheduled Tribe question in the Nilgiris ([The News Minute](https://www.thenewsminute.com/article/nilgiri-tribes-oppose-st-status-badagas-question-their-unique-identity-status-164627)).
- Characters are never labelled as "indigenous" or "not indigenous".

### Conflict-affected regions
- **Manipur** has had ethnic violence between the Meitei and Kuki-Zo communities since May 2023 ([ThePrint](https://theprint.in/india/306-killed-49-missing-in-ethnic-violence-since-may-2023-manipur-home-minister-tells-assembly/3032471/)).
- Every Manipur community gets its own neutral, everyday entries. No conflict imagery, no armed or protest scenes, and no community presented as "the real Manipur".
- The same rule applies to Jammu & Kashmir and to any region with an active conflict: everyday life, homes, work, festivals, nothing else.

### Religion
- Each state's characters follow its real religious makeup, using census figures stored in `religion_mix`.
- Articles of faith are shown only correctly and only on members of that faith, never as decoration. Examples: a Sikh turban and kada, a hijab or skullcap, a cross, Buddhist robes, Jain symbols, tilak styles of different Hindu traditions.

### Marriage, widowhood and life stages
- Marital symbols (sindoor, mangalsutra, thali, toe rings and others) carry `meaning: ["marital"]` and `requires.marital_status`.
- They are never put on unmarried characters or on children.
- Mourning and widowhood dress is flagged `mourning` and used only when the scene calls for it. A widowed character is not shown only in mourning.

### Caste
- Characters are **never** labelled by caste, and dress or occupations are never tied to caste.
- In many regions surnames signal caste ([The Federal, on Kerala names](https://thefederal.com/category/the-eighth-column/kerala-names-surname-religion-caste-identity-hindu-muslim-christian-politics-communist-cpim-245204)). Characters therefore use a father's name or a house-name initial as their second name, never a caste surname.

### The Northeast
- Each of the eight states has many distinct communities with their own dress, languages and looks. Never use one generic "Northeast" look, and never treat the region as exotic.

---

## 3. Per-state source lists
The full source list for each state is inside its region file (`data/regions/<state>.json`, field `sources`), with the date each source was checked.
