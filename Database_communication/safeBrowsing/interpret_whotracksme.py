import time

import requests
from flask import jsonify, config
import database_playground
import json
from pprint import pprint
import ast
import threading

preferences = {"whotracksme": ["FacebookWTM", "AmazonWTM"], "privacyspy": [], "google_safeBrowsing": [],
               "phishstats": [],
               "tosdr": [],
               "Tilthub": []}

expert_mode = False


def change_prefs(prefs):
    global preferences
    preferences = prefs


def change_expert(expert):
    global expert_mode
    expert_mode = expert


def generic_sql_query(query, db):
    cursor = db.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    return rows


def get_domain_by_url(url):
    if url.__contains__("www."):
        url = url.replace("www.", "")
    url = url.split("/")[0]
    url_split = url.split(".")
    if len(url_split) >= 3:
        url_split.pop(0)
    url = ".".join(url_split)
    return url


def build_user_linking_string(unwanted_categories):
    unwanted_categories.sort()
    db_string = ""
    for category in unwanted_categories:
        db_string += str(category)
    return db_string


def dict_to_string(dict):
    end_string = ""
    for key in dict:
        if dict[key]:
            dict[key] = dict[key].sort()
            end_string += key + str(dict[key])


##################################################################################################################################
#                                                      MAIN METHOD                                                               #
##################################################################################################################################

def backend_main(domain_list):
    start = time.time()
    unwanted_categories = []  # just temporary
    # global config
    # config = dotenv_values(".env")  # take environment variables from .env.
    # domain_dict = {}
    # db = database_playground.connect_db_labels()
    data_summary = {}
    # db_string = build_user_linking_string(unwanted_categories)

    newlabelsdb = database_playground.connect_new_labels()

    for domain in domain_list:

        query = f"SELECT domain FROM dict where domain = '{domain}' AND preferences = '{json.dumps(preferences)}';"
        doma = generic_sql_query(query, newlabelsdb)
        data_summary[domain] = []

        if doma and not expert_mode:
            query = f"SELECT name FROM columns;"
            columns = generic_sql_query(query, newlabelsdb)
            cnt = columns.__len__()
            dontAdd = True
            for i in range(cnt):
                col = columns[i]

                query = f"SELECT {col[0]} FROM dict where domain = '{domain}';"

                partialDict = generic_sql_query(query, newlabelsdb)
                strDict = (partialDict[0])[0]
                newDict = json.loads(strDict)
                if dontAdd:  # removes first elem of dict
                    dontAdd = False
                    continue
                data_summary[domain].append(newDict)

        if not data_summary[domain]:
            label_max = 3

            if expert_mode:
                label_max = 9

            whotracksme = whotracksme_score(domain, unwanted_categories)
            phishstats = phishstats_score(domain)
            privacyspy = privacyspy_score(domain)
            tosdr = tosdr_score(domain)
            tilt = tilthubScore(domain)

            calced_label = calc_label(label_max, [whotracksme, phishstats, privacyspy, tosdr,
                                                  tilt])  # google_safe_browsing_score(domain)])

            dictionary = {
                             "label": calced_label}, whotracksme, phishstats, privacyspy, tosdr, tilt  # google_safe_browsing_score(domain)

            data_summary[domain] = dictionary

            if not expert_mode:
                saveCalcLabels(dictionary, domain)

            # domain_dict[domain] = data_summary[domain][0]["whotracksme.db"]["label"]
            # domain_dict[domain] = score        # + phishstats_score(domain)
            # if you have configured api keys from google and rapid and have stored the keys in textfile
            # called .env you can use the line below and the first two lines in this function.
            # If you not you should comment it to avoid errors
            # domain_dict[domain] += int(phishstats_score(domain)["phishstats.db"]["label"])
            # domain_dict[domain] += google_safe_browsing_score(domain) + web_risk_api_score(domain)

    # pprint(data_summary)
    end = time.time()
    print(end - start)
    return json.dumps(data_summary)  # json.dumps(domain_dict)


##################################################################################################################################
#                                                      DATABASE                                                                  #
##################################################################################################################################

def calc_label(label_max, db_array):
    res = 0
    no_data = 0
    for db in db_array:
        res += int(list(db.values())[0]['score'])
        if int(list(db.values())[0]['score']) == 0:
            no_data += 1
    if res == 0:
        return 0
    res = res / (len(db_array) - no_data)
    if res > label_max:
        res = label_max
    if res != 0 and res.__round__() == 0:
        res = 1
    else:
        res = res.__round__()
    # print(res)
    return res


def saveCalcLabels(data_summary, domain):
    db = database_playground.connect_new_labels()

    lenList = data_summary.__len__()
    query = f"INSERT INTO columns (name) SELECT 'preferences' WHERE NOT EXISTS (SELECT name FROM columns WHERE name = 'preferences');"  # we have to store the labels together with the preferences
    cursor = db.cursor()
    cursor.execute(query)
    db.commit()
    try:
        query = f"ALTER TABLE dict ADD preferences varchar(999);"  # create row preferences
        cursor = db.cursor()
        cursor.execute(query)
        db.commit()

        query = f"UPDATE dict SET preferences = '{json.dumps(preferences)}' where domain = '{domain}';"  # map preferences to domain

        cursor = db.cursor()
        cursor.execute(query)
        db.commit()

    except:
        # query = f"replace INTO dict ({key}) VALUES ('{dictString}');"
        query = f"UPDATE dict SET preferences = '{json.dumps(preferences)}' where domain = '{domain}';"  # map preferences to domain

        cursor = db.cursor()
        cursor.execute(query)
        db.commit()

    for i in range(lenList):
        dict = data_summary[i]

        dictString = json.dumps(dict)

        start = dictString.find('"') + 1
        end = dictString.find('"', start)
        key = dictString[start:end]

        if key[-3:] == '.db':
            key = dictString[start:end - 3]

        query = f"INSERT INTO dict (domain) SELECT '{domain}' WHERE NOT EXISTS (SELECT domain FROM dict WHERE domain = '{domain}');"
        cursor = db.cursor()
        cursor.execute(query)
        db.commit()

        query = f"INSERT INTO columns (name) SELECT '{key}' WHERE NOT EXISTS (SELECT name FROM columns WHERE name = '{key}');"
        cursor = db.cursor()
        cursor.execute(query)
        db.commit()

        try:
            query = f"ALTER TABLE dict ADD \"{key}\" varchar(999);"
            cursor = db.cursor()
            cursor.execute(query)
            db.commit()

            query = f"update dict set {key} = '{dictString}' where domain = '{domain}';"
            cursor = db.cursor()
            cursor.execute(query)
            db.commit()

        except:

            # query = f"replace INTO dict ({key}) VALUES ('{dictString}');"
            query = f"update dict set {key} = '{dictString}' where domain = '{domain}';"
            cursor = db.cursor()
            cursor.execute(query)
            db.commit()
            continue

    """whotracksme_label = data_summary[0]["whotracksme.db"]["score"]
    tracker_cnt = data_summary[0]["whotracksme.db"]["tracker_count"]
    amzn = data_summary[0]["whotracksme.db"]["amazon"]
    fcbook = data_summary[0]["whotracksme.db"]["facebook"]


    phishstats_label = data_summary[1]["phishstats.db"]["score"]
    phishing_category = data_summary[1]["phishstats.db"]["category"]

    privacyspy_score = str(data_summary[2]["privacyspy"]["score"])"""

    """query = f"REPLACE INTO labels (domain, calced_label, whotracksme_score, tracker_count, amazon, facebook, phishstats_score, phishing_category, privacyspy_score) VALUES (\"{domain}\", \"{label}\" , \"{whotracksme_label}\", \"{tracker_cnt}\", \"{fcbook}\", \"{amzn}\", \"{phishstats_label}\", \"{phishing_category}\" , \"{privacyspy_score}\");"
    cursor = db.cursor()
    cursor.execute(query)
    db.commit()"""


def fill_label_database(domain_dict, users):
    db = database_playground.connect_db_labels()
    # print(domain_dict)
    for key in domain_dict:
        # print(key)
        query = f"REPLACE INTO domain_data (domain, label, users) VALUES (\"{key}\", \"{domain_dict[key]}\", \"{users}\");"
        cursor = db.cursor()
        cursor.execute(query)
        db.commit()


##################################################################################################################################
#                                                      SCORE METHODS                                                             #
##################################################################################################################################

def whotracksme_score(domain, unwanted_categories):
    # print(preferences)
    query_trackers = f"SELECT sites_trackers_data.tracker AS tracker, categories.name AS category, companies.name AS Company_name, https FROM trackers, categories, sites_trackers_data, companies WHERE trackers.category_id = categories.id AND trackers.company_id = companies.id AND trackers.id = sites_trackers_data.tracker AND sites_trackers_data.site =\"{domain}\""
    db = database_playground.connect_db()
    trackers = generic_sql_query(query_trackers, db)

    data_summary = {
        "whotracksme.db": {
            "score": "0",
            "tracker_count": "0",
            "facebook": "",
            "amazon": "",
            "trackers": []
        }}
    if preferences["whotracksme"]:
        if "disableWTM" in preferences["whotracksme"]:
            return data_summary
    max_index = 3
    expert_weight = 1

    if expert_mode:
        expert_weight = 2.5  # multiplier for the expert mode
        max_index = 9
    facebook_amazon_weight = 0.5 * expert_weight
    category_weight = 2 * expert_weight
    https_weight = 1.5 * expert_weight
    tracker_multiplier_weight = 0.1 * expert_weight
    https_avg = 0
    index = 0
    facebook = False
    amazon = False
    https_all_tracker = 0
    for cookie in trackers:
        # (cookie[3])
        for category in unwanted_categories:
            if cookie in category:
                index += category_weight
        # if preferences["whotracksme"]:
        if "FacebookWTM" in preferences["whotracksme"] and cookie.__contains__("Facebook"):
            index += facebook_amazon_weight
            facebook = True
        if "AmazonWTM" in preferences["whotracksme"] and cookie.__contains__("Amazon"):
            index += facebook_amazon_weight
            amazon = True
        https_all_tracker += cookie[3]
    if trackers and "weight_httpsWTM" in preferences["whotracksme"]:
        https_avg = https_all_tracker / len(trackers)
        if https_avg < 0.7:  # means that less than 70 percent of the domains tracker use the https protocoll
            index += https_weight

    # if preferences["whotracksme"]:
    if "weight_trackerWTM" in preferences["whotracksme"]:
        tracker_multiplier_weight = tracker_multiplier_weight * 2

    cookie_len = len(list(filter(lambda a: not a.__contains__("essential"), trackers)))
    index += cookie_len * tracker_multiplier_weight

    if index > max_index:
        index = max_index
    if index != 0 and index.__round__() == 0:
        index = 1
    index = index.__round__()

    for i in trackers:
        data_summary["whotracksme.db"]["trackers"] += [{  # Fill trackers array
            "name": i[0],
            "category": i[1],
            "company": i[2],
        }]

    data_summary["whotracksme.db"]["score"] = eval(str(index))
    data_summary["whotracksme.db"]["tracker_count"] = eval(str(len(trackers)))
    data_summary["whotracksme.db"]["facebook"] = eval(str(facebook))
    data_summary["whotracksme.db"]["amazon"] = eval(str(amazon))
    data_summary["whotracksme.db"]["https_avg"] = eval(str(https_avg))

    return data_summary


def tilthubScore(domain):
    split = domain.split(".")
    name = split[0]
    # req = f"http://ec2-18-185-97-19.eu-central-1.compute.amazonaws.com:8080/tilt/tilt?filter={{'meta.url' : '{name}'}}"
    req2 = "http://ec2-18-185-97-19.eu-central-1.compute.amazonaws.com:8080/tilt/tilt"

    response = requests.get(req2, auth=("admin", "secret"))

    tiltDict = json.loads(response.content)

    data_summary = {
        "tilthub": {
            "score": "0",
            "Data Disclosed": "",
            "Third Country Transfers": "",
            "Right to Withdraw Consent": "",
            "Right to Complain": "",
            "Data Protection Officer": "",
            "Right to Data Portability": "",
            "Right to Information": "",
            "Right to Rectification or Deletion": "",
            "Automated Decision Making": "",
        }}

    length = len(tiltDict)
    # listOfIndices = []
    if expert_mode:
        adder = 1
    else:
        adder = 0.3
    calcedScore = 0
    for i in range(length):
        url = tiltDict[i]["meta"]["url"].split("//")[1]
        calcedDomain = get_domain_by_url(url)
        if calcedDomain == domain:
            tiltInfos = tiltDict[i]

            data_summary["tilthub"]["Right to Complain"] = str(tiltInfos["rightToComplain"]["available"])
            if not tiltInfos["rightToComplain"]["available"]:
                calcedScore += adder

            data_summary["tilthub"]["Data Protection Officer"] = str(tiltInfos["dataProtectionOfficer"]["name"])
            if tiltInfos["dataProtectionOfficer"]["name"] is None:
                calcedScore += adder

            data_summary["tilthub"]["Third Country Transfers"] = str(len(tiltInfos["thirdCountryTransfers"]))
            if not len(tiltInfos["thirdCountryTransfers"]) > 1:
                calcedScore += adder

            data_summary["tilthub"]["Right to Withdraw Consent"] = str(tiltInfos["rightToWithdrawConsent"]["available"])
            if not tiltInfos["rightToWithdrawConsent"]["available"]:
                calcedScore += adder

            data_summary["tilthub"]["Right to Data Portability"] = str(tiltInfos["rightToDataPortability"]["available"])
            if not tiltInfos["rightToDataPortability"]["available"]:
                calcedScore += adder

            data_summary["tilthub"]["Right to Information"] = str(tiltInfos["rightToInformation"]["available"])
            if not tiltInfos["rightToInformation"]["available"]:
                calcedScore += adder

            data_summary["tilthub"]["Right to Rectification or Deletion"] = str(
                tiltInfos["rightToRectificationOrDeletion"]["available"])
            if not tiltInfos["rightToRectificationOrDeletion"]["available"]:
                calcedScore += adder

            data_summary["tilthub"]["Automated Decision Making"] = str(tiltInfos["automatedDecisionMaking"]["inUse"])
            if not tiltInfos["automatedDecisionMaking"]["inUse"]:
                calcedScore += adder

            """data_summary["tilthub"]["Data Disclosed"] = str(tiltInfos["rightToComplain"]["available"])
            if tiltInfos["rightToComplain"]["available"]:
                calcedScore += adder"""
            break

    if not expert_mode:
        calcedScore = int(round(calcedScore))

    data_summary["tilthub"]["score"] = str(calcedScore)

    return data_summary


# new database tosdr:https://tosdr.org/
# https://tosdr.org/de/service/230 Expert Mode
def tosdr_score(domain):
    data_summary = {
        "tosdr": {
            "score": "0",
            "name": "",
            "link": ""
        }}

    with open("tosdr.json", encoding="utf8") as file:
        data = json.load(file)
    for elem in data["parameters"]["services"]:
        if domain in elem["urls"]:
            data_summary["tosdr"]["score"] = map_tosdr_score(elem["rating"])
            data_summary["tosdr"]["name"] = elem["name"]
            data_summary["tosdr"]["link"] = "https://tosdr.org/de/service/" + str(elem["id"])

    return data_summary


def map_tosdr_score(rating):
    label_max = 3
    if expert_mode:
        label_max = 9
    switcher = {
        'A': 1 * label_max / 5,  # +0.1 as it is not supposed to be 0 elem['score']) * label_max/10
        'B': 2 * label_max / 5,
        'C': 3 * label_max / 5,
        'D': 4 * label_max / 5,
        'E': 5 * label_max / 5
    }
    if switcher.get(rating, "0") != "0":
        return (switcher.get(rating, "0") / 5) * 3
    else:
        return "0"


def privacyspy_score(domain):
    data_summary = {
        "privacyspy": {
            "score": "0",
            "name": "",
            "link": ""
        }}
    if preferences["privacyspy"]:
        if "disablePrsspy" in preferences["privacyspy"]:
            return data_summary
    label_max = 3
    if expert_mode:
        label_max = 9
    with open("privacyspy.json", encoding="utf8") as file:
        data = json.load(file)
    for elem in data:
        if domain in elem["hostnames"]:
            data_summary["privacyspy"]["score"] = (10 - elem["score"]) * label_max / 10
            data_summary["privacyspy"]["name"] = elem["name"]
            data_summary["privacyspy"]["link"] = "https://privacyspy.org/product/" + str(elem["slug"])

    return data_summary


def api_call(request, payload, body, type):
    if type == "POST":
        response = requests.post(request, data=payload, json=body)
    elif type == "GET":
        response = requests.get(request)
    return response.json()


def phishstats_score(domain):
    query = f"SELECT score, url from phish_score where URL like '%{domain}%'"
    db = database_playground.connect_phishcore_db()
    req = generic_sql_query(query, db)
    data_summary = {
        "phishstats.db": {
            "score": "0",
            "category": "no info",
            "phishing": "false"
        }}
    if not req:
        return data_summary

    if preferences["phishstats"]:
        if "disablePhish" in preferences["phishstats"]:
            return data_summary
    length = req.__len__()
    domainPresent = False

    for i in range(length):

        url = (req[i][1]).split("//")[1]
        comparison = get_domain_by_url(url)
        if domain == comparison:
            domainPresent = True
            break

    if not domainPresent:
        return data_summary

    score = req[i][0]

    num = float(score.replace("\"", ""))
    '''
    If there is a result in the database the domain is definetely sus. Therefore, we ignore the label and return the wort label right away.



        if num <= 2:
        data_summary['phishstats.db']['score'] = eval(str(2))
        data_summary['phishstats.db']['category'] = "possibly phishing"

    elif num <= 4 and num > 2:
        data_summary['phishstats.db']['score'] = eval(str(2))
        data_summary['phishstats.db']['category'] = "sus"

    elif num <= 6 and num > 4:
        data_summary['phishstats.db']['score'] = eval(str(3))
        data_summary['phishstats.db']['category'] = "probably phishing"

    else:
        data_summary['phishstats.db']['score'] = eval(str(3))
        data_summary['phishstats.db']['category'] = "guaranteed phishing"
        data_summary['phishstats.db']['phishing'] = "True"

    if expert_mode:
        data_summary['phishstats.db']['score'] = eval(str(num))
    '''
    data_summary["phishstats.db"]["category"] = "Be aware of phishing"

    if expert_mode:
        data_summary["phishstats.db"]["score"] = eval(str(9))
    else:
        data_summary["phishstats.db"]["score"] = eval(str(3))

    return data_summary


def google_safe_browsing_score(domain):
    data_summary = {
        "safe_browsing_api": {
            "score": "0",
            "threatType": "",
            "platform": ""
        }}
    if preferences["google_safeBrowsing"]:
        if "diableGoogle" in preferences["google_safeBrowsing"]:
            return data_summary

    body = {
        "client": {
            "clientId": "ProgPrak",
            "clientVersion": "141"
        },
        "threatInfo": {
            "threatTypes": ["THREAT_TYPE_UNSPECIFIED", "MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE",
                            "POTENTIALLY_HARMFUL_APPLICATION"],
            "platformTypes": ["WINDOWS", "LINUX", "OSX", "IOS", "CHROME"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [
                {
                    "url": f"{domain}"},
            ]
        }
    }
    response = api_call(f" https://safebrowsing.googleapis.com/v4/threatMatches:find?key={config['GOOGLE_API_KEY']}",
                        None, body,
                        "POST")
    # print(response)
    if response:
        # print(response)
        data_summary["safe_browsing_api.db"]["score"] = '3'
        data_summary["safe_browsing_api.db"]["threatType"] = response["matches"][0]["threatType"]
        data_summary["safe_browsing_api.db"]["platform"] = response["matches"][0]["platformType"]

    return 0


def web_risk_api_score(domain):
    data_summary = {
        "safe_browsing_api": {
            "score": "0",
            "threatType": "",
            "platform": "",

        }}
    if preferences["google_safeBrowsing"]:
        if "diableGoogle" in preferences["google_safeBrowsing"]:
            return data_summary
    url = "https://wot-web-risk-and-safe-browsing.p.rapidapi.com/targets"

    querystring = {"t": domain}

    headers = {
        "x-rapidapi-key": config["RAPID_API_KEY"],
        "x-rapidapi-host": "wot-web-risk-and-safe-browsing.p.rapidapi.com"
    }

    response = requests.request("GET", url, headers=headers, params=querystring)
    print(response.json())
    return 0
