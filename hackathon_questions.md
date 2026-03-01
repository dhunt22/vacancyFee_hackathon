# Hackathon Planning Questions

Please answer below each question. Leave blank if unsure — we can revisit.

---

## Participants & Registration

**1. How many attendees are you expecting?**
> 5

**2. What's the expected skill breakdown? (e.g., mostly beginners, mostly technical, a mix?)**
> mostly beginners

**3. Is registration open yet? Are you collecting skill/interest info during registration so you can pre-plan team formation?**
> yes, did not collect participation information

**4. Will participants bring their own laptops, or do you need to provide machines?**
>participants will supply their own machines

---

## Venue & Format

**5. In-person, virtual, or hybrid?**
>in-person

**6. If in-person — do you have a venue locked down? How's the WiFi capacity, power outlet availability, and seating arrangement?**
>all locked down, hosted at someone's house

**7. Will there be food/drinks?**
>yes

**8. What's the date? How much lead time do you have to prepare?**
>1 day

---

## Data Preparation (Critical)

**9. Have you identified which parcels are "vacant" yet? Has anyone done the filtering, or is that prep work you still need?**
>we have only done an initial look at the data, there seems to be many parcels that are not flagged vacant that should be (i.e. dilapidated buildings, houses, or empty commercial structure that has not been leased in 1+ years however, is still a viable structure

**10. The CSV is 986 MB with 270+ columns. Participants can't work with that raw file — especially beginners on Google Sheets. Do you want me to build pre-filtered, simplified datasets?** (e.g., a small "vacant parcels only" CSV, a Google Sheets-ready version, a GeoJSON for mapping projects)
>Yes, build a pre-filtered version by reducing columns. We have the raw dataset on google drive. The trimmed version will also be uploaded there. Also create a geojson and KMZ file for geospatial exploration.

**11. The "Resources to Prepare" checklist in the plan is entirely unchecked — council district boundaries, neighborhood boundaries, pre-filtered subsets, etc. What's your status on these?**
>We have council district boundaries and an old subset of parcels. With this new data we will have a different subset of parcels. I added the district boundaries to the data folder here, try fetching Sacramento neighborhood boundaries from the county or California GIS data portal. I also added 311 call data (to be correlated with vacant areas), basemap data (OSM roads and buildings).

**12. The Tax Roll zips contain secured/unsecured rolls and a transfer list. Are these meant for participants, or are they your source data that gets merged into the main CSV?**
>These can be used by participants, lets keep them separate since they are also large tables. Figure out a simple way to integrate this.

---

## Technical Infrastructure

**13. For beginner tracks (Google Sheets, Canva) — will you provide a shared Google Drive folder with ready-to-use data files?**
>Yes, help me with preparing the files and other setup for those platforms.

**14. For intermediate mapping projects (Felt, Google My Maps) — these tools have row limits (Felt caps ~5K rows on free plans). Should I prepare appropriately sized subsets?**
>Let's not use Felt, just Google my Maps, Google Earth Pro, and QGIS. We will need to write basic install information for QGIS.

**15. For advanced tracks — do you want me to build a starter code repo with Python notebooks that load the data and do basic filtering so coders can jump straight in?**
>Yes, notebooks are a good format. Keep python libraries stack simple (pandas, geopandas, matplotlib for maps, etc...)

**16. The GeoPackage is 198 MB in EPSG:2226. Should I prepare a lighter-weight version for QGIS users, or is that manageable?**
>Geometries in the parcel file are the main bottleneck, try making a version with simplified geometry and spatial indexing for better performance. the original parcel file is manageable as-is.

---

## Accessibility & Inclusion

**17. What does "accessible" mean for your goals? Physical accessibility? Skill-level accessibility? Language accessibility?**
>Skill level, mainly

**18. Several advanced projects (A3, A4, A6) seem very ambitious for 1 hr 45 min of hacking. Are you okay with proof-of-concept outputs, or should we scope them down with clearer "minimum viable deliverable" definitions?**
>I think some exercises can be run via other coders using AI heavily, leave the few advanced projects as an exercise for them. I will be working on an advanced project while leading the hackathon.

**19. Project B4 (Photo Documentary) asks people to physically go out into the community. Is that realistic in a 3-hour window, or should it be reframed as Street View-only?**
>Some vacant lots are within a 10 minute walk, most of town can be reached within 10 minutes of biking, too. We think people could document a handful of sites each.

---

## Team Formation & Mentoring

**20. How will teams form? Self-selection, pre-assigned based on registration, or facilitated matching?**
>We may not have 'teams' it may be just be self-selection and people availability.

**21. Will there be mentors/facilitators circulating during the hack?**
>There will be another mentor who is more knowledgeable on VacancyFee. We will both be circulating

**22. With 18 project options and possibly small attendance, are you worried about spreading too thin? Would it be better to curate a shorter list of 6-8 recommended projects?**
>Yes, reduce the project count to 5 distinct.

---

## Judging & Deliverables

**23. Who are the judges?**
>This is not a standard hackathon and will not really be judged.

**24. How will teams present? Screen-share? Walk around to tables? Printed outputs?**
>Teams will screen-share or run a PowerPoint through a large TV.

**25. Is there a prize or incentive structure, or is voting purely for recognition?**
>No, this is just a collaborative event, also to recognize work towards the project.

**26. How will you collect deliverables after the event?**
>Google Drive

---

## Post-Hackathon & Outputs

**27. Do you have someone who can take hackathon outputs and publish them to vacancyfee.org? Or does the hackathon need to produce publish-ready artifacts?**
>Yes, I and the other mentor will perform a final polish to then post to the website and use for social media campaigns.

**28. Does VacancyFee.org have brand guidelines, colors, logos, or fonts that teams should use?**
>No

---

## Anything Else

**29. Any other constraints, goals, or ideas you want to flag?**
>No
