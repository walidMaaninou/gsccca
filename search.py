import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
from datetime import datetime, timedelta


def search_documents(session: requests.Session, instrument_type: int, county_id: int, date_from: str, date_to: str):
    url = "https://search.gsccca.org/RealEstatePremium/InstrumentTypeSearchResults.aspx"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://search.gsccca.org/RealEstatePremium/InstrumentTypeSearch.aspx",
        "Origin": "https://search.gsccca.org",
    }

    init_response = session.get(url, headers=headers, verify=False)
    soup = BeautifulSoup(init_response.text, "html.parser")

    viewstate = soup.find(id="__VIEWSTATE")["value"]
    eventvalidation = soup.find(id="__EVENTVALIDATION")["value"]
    viewstategenerator = soup.find(id="__VIEWSTATEGENERATOR")["value"]
    previous_page = soup.find(id="__PREVIOUSPAGE")["value"]

    payload = {
        "__VIEWSTATE": viewstate,
        "__VIEWSTATEGENERATOR": viewstategenerator,
        "__EVENTVALIDATION": eventvalidation,
        "__PREVIOUSPAGE": previous_page,
        "__EVENTTARGET": "ctl00$BodyContent$lvDashboard$btnExpandAllDetails",
        "__EVENTARGUMENT": "",
        "__LASTFOCUS": "",

        "ctl00$BodyContent$ddlInstrumentTypes": str(instrument_type),
        "ctl00$BodyContent$ddlCounties": str(county_id),
        "ctl00$BodyContent$txtDateFrom": date_from,
        "ctl00$BodyContent$txtDateTo": date_to,
        "ctl00$BodyContent$txtSectionGMD": "",
        "ctl00$BodyContent$txtDistrict": "",
        "ctl00$BodyContent$txtLandLot": "",
        "ctl00$BodyContent$ddlRecordsPerPage": "100",
        "ctl00$BodyContent$ddlDisplayType": "1",
        "ctl00$BodyContent$btnSearch": "Begin Search",
        "ctl00$BodyContent$chkExpand": "on"
    }

    search_response = session.post(url, data=payload, headers=headers, verify=False)
    with open("results.html", "w", encoding="utf-8") as f:
        f.write(search_response.text)
    return search_response.text


def extract_combined_image_urls_with_subdivision_and_grantee(html: str):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    dash_tables = soup.find_all("table", class_="DashboardTable")
    print(len(dash_tables))

    if not dash_tables:
        return [], 0

    for dashtable in dash_tables:
        has_subdivision = False

        for tr in dashtable.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue

            for td in tds:
                text = td.get_text(strip=True).upper()

                # Detect subdivision
                if "SUBDIVISION:" in text:
                    span = td.find("span")
                    if span and span.get_text(strip=True):
                        has_subdivision = True

                # Detect grantee span
                if span := td.find("span", id=re.compile("BodyContent_lvDashboard_lvExpandedGrantee_.*_lblGranteeName_")):
                    name = span.get_text(strip=True)
                    if name:
                        grantee = name
                        break

        # if has_subdivision:
        if True:
            link = dashtable.find("a", onclick=True)
            if link:
                match = re.search(r"ViewCombinedImages\('([^']+)'", link["onclick"])
                if match:
                    results.append({
                        "doc_id": match.group(1),
                        "grantee": grantee
                    })

    return results, len(dash_tables)


def extract_filed_dates(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    filed_dates = []
    for td in soup.find_all("td"):
        if "Filed" in td.text:
            span = td.find("span", id=re.compile("BodyContent_lvDashboard_lblDateFiled_"))
            if span and span.text.strip():
                filed_dates.append(span.text.strip())
    return filed_dates


def loop_document_scrape(session, instrument_type, county_id, start_date, end_date):
    all_doc_urls = []
    current_from = datetime.strptime(start_date, "%m/%d/%Y")
    final_to = datetime.strptime(end_date, "%m/%d/%Y")

    while current_from <= final_to:
        str_from = current_from.strftime("%m/%d/%Y")
        str_to = final_to.strftime("%m/%d/%Y")
        print(f"Searching from {str_from} to {str_to}")

        html = search_documents(session, instrument_type, county_id, str_from, str_to)
        filed_dates = extract_filed_dates(html)
        results, total_docs = extract_combined_image_urls_with_subdivision_and_grantee(html)

        print(f"  Found {total_docs} documents.")

        all_doc_urls.extend(results)

        if total_docs < 100 or not filed_dates:
            break  # Done: either no pagination or no more results

        try:
            # Move to day after last filed date to avoid duplicates
            last_date = max(datetime.strptime(d, "%m/%d/%Y") for d in filed_dates)
            current_from = last_date + timedelta(days=1)
        except Exception as e:
            print(f"Error parsing filed dates: {e}")
            break

    return all_doc_urls
