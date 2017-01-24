# -*- coding: utf-8 -*-
import os
import sys
import urllib
import xbmc
import xbmcaddon
import xbmcgui, xbmcplugin
import xbmcvfs
import re, shutil, requests, cgi
from bs4 import BeautifulSoup

# Globals
addon = xbmcaddon.Addon()
base_url = sys.argv[0]
addon_handle = int(sys.argv[1])
addonID = addon.getAddonInfo('id')
translation = addon.getLocalizedString
profile = xbmc.translatePath(addon.getAddonInfo('profile')).decode("utf-8")
temp = xbmc.translatePath(os.path.join(profile, 'temp', '')).decode("utf-8")
cwd = xbmc.translatePath(addon.getAddonInfo('path')).decode("utf-8")
resource = xbmc.translatePath(os.path.join(cwd, 'resources', 'lib')).decode("utf-8")
icon = xbmc.translatePath('special://home/addons/' + addonID + '/icon.png')
subdir = xbmc.translatePath(os.path.join(temp, 'subs', '')).decode("utf-8")
subdownload = xbmc.translatePath(os.path.join(temp, 'download', '')).decode("utf-8")
subtitlefile = "subcentral"
mainUrl = "https://www.subcentral.de"

# Anlegen von Directorys
if xbmcvfs.exists(subdir):
    shutil.rmtree(subdir)
xbmcvfs.mkdirs(subdir)

if xbmcvfs.exists(subdownload):
    shutil.rmtree(subdownload)
xbmcvfs.mkdirs(subdownload)

if xbmcvfs.exists(temp):
    shutil.rmtree(temp)

xbmcvfs.mkdirs(temp)
xbmcvfs.mkdirs(subdir)
xbmcvfs.mkdirs(subdownload)


# Logging
def debug(content):
    log(content, xbmc.LOGDEBUG)


def notice(content):
    log(content, xbmc.LOGNOTICE)


def log(msg, level=xbmc.LOGNOTICE):
    addon = xbmcaddon.Addon()
    addonID = addon.getAddonInfo('id')
    xbmc.log('%s: %s' % (addonID, msg), level)


def ersetze(inhalt):
    inhalt = inhalt.replace('&#39;', '\'')
    inhalt = inhalt.replace('&quot;', '"')
    inhalt = inhalt.replace('&gt;', '>')
    inhalt = inhalt.replace('&amp;', '&')
    inhalt = inhalt.strip()
    return inhalt


# Einstellungen Lesen
def getSettings():
    global user
    user = addon.getSetting("user")
    global pw
    pw = addon.getSetting("pw")
    global backNav
    if user == "" or pw == "":
        xbmcgui.Dialog().notification("Tv4user.de", "Username or Pw is empty", xbmcgui.NOTIFICATION_ERROR,
                                      5000);
        addon.openSettings()
        sys.exit()


# Url Parameter Einlesen
def get_params(string=""):
    param = []
    if string == "":
        paramstring = sys.argv[2]
    else:
        paramstring = string
    if len(paramstring) >= 2:
        params = paramstring
        cleanedparams = params.replace('?', '')
        if (params[len(params) - 1] == '/'):
            params = params[0:len(params) - 2]
        pairsofparams = cleanedparams.split('&')
        param = {}
        for i in range(len(pairsofparams)):
            splitparams = {}
            splitparams = pairsofparams[i].split('=')
            if (len(splitparams)) == 2:
                param[splitparams[0]] = splitparams[1]

    return param


# Einloggen
def login():
    global session
    session = requests.Session()
    headers = {'user-agent': 'Mozilla', 'Content-Type': 'application/x-www-form-urlencoded'}
    payload = {'form': 'UserLogin', 'loginUsername': user, 'loginPassword': pw, 'useCookies': '1'}
    r = session.post(mainUrl + "/index.php", headers=headers, data=payload)
    debug("Login response: " + str(r))
    debug("Set-Cookie: "+r.headers["Set-Cookie"])


# Url einlesen
def getUrl(url):
    r = session.get(url)
    debug("getUrl response: " + str(r))
    return r.content

    # Titel Beeinigen


def clean_serie(title):
    title = title.lower().replace('the ', '')
    title = title.replace('.', '')
    title = title.replace("'", "")
    title = title.replace("&amp;", "")
    title = title.strip()
    return title


# Liste Aller Serien Holen
def lies_serien():
    debug("Subcentral: Starte ShowAllSeries")
    content = getUrl(mainUrl + "/index.php")
    content = content[content.find('<option value=""> Serien-QuickJump </option>') + 1:]
    content = content[:content.find('</form>')]
    # Serie Suchen
    match = re.compile('<option value="([0-9]+?)">([^<>]+?)</option>', re.DOTALL).findall(content)
    threadIDs = []
    threadNames = []
    threadNamesclean = []
    for id, title in match:
        threadIDs.append(id)
        # Clean wird gebraucht damit "The und ohen The Serien Matchen"
        threadNamesclean.append(clean_serie(title))
        threadNames.append(ersetze(title))
    threadIDs, threadNames, threadNamesclean = (list(x) for x in
                                                zip(*sorted(zip(threadNames, threadIDs, threadNamesclean))))
    return threadIDs, threadNames, threadNamesclean


# Einen Link Erzeugen
def addLink(name, url, mode, icon="", duration="", desc="", genre='', lang=""):
    u = sys.argv[0] + "?url=" + urllib.quote_plus(url) + "&mode=" + str(mode)
    ok = True
    iconl = ""
    sprache = ""
    if lang == "de":
        sprache = translation(30110)
        iconl = "de"
    else:
        sprache = translation(30111)
        iconl = "en"
    liz = xbmcgui.ListItem(label2=name, thumbnailImage=iconl, label=sprache)
    debug("ICON:" + icon)
    ok = xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz)
    return ok


# Alle Folgen  Holen je nachdem ob englisch oder Deutsch
def list_folgen(url):
    debug("list_folgen: " + url)
    content = getUrl(url)
    # debug("Content"+content)
    xbmcgui.Dialog().notification("Tv4user.de", "lade subtitle...", xbmcgui.NOTIFICATION_INFO,
                                  5000);
    htmlPage = BeautifulSoup(content, 'html.parser')

    divs = htmlPage.find_all('div', id=re.compile('a\d'))
    if len(divs) < 1:
        quoteBody = htmlPage.find_all("div", class_="quoteBody")
        # debug("QuoteBody: " +str(quoteBody))
        divs = quoteBody[0].find_all('table')
        # debug("divs: " + str(divs))
    for div in divs:
        debug("DIV: "+str(div))
        isInaktiv = div.find_all("tr", class_="inaktiv")
        if isInaktiv:
            continue
        trs = div.find_all('tr')
        imgs = trs[0].find_all('img')
        for tr in trs:
            subLinks = tr.find_all('a')
            titles = tr.find_all("td", class_="release")
            if titles is None or len(titles)<1:
                continue
            episodeTitle = titles[0].string
            for link, img in zip(subLinks, imgs):
                    subLink = link.get('href')
                    author = link.string
                    imgSrc = img.get('src')
                    release = img.parent.contents[1]
                    match = re.compile('flags\/(.*?)\.', re.DOTALL).findall(imgSrc)
                    language = match[0]
                    debug("episodeTitle: " + str(episodeTitle))
                    debug("subLink: " + str(subLink))
                    debug("author: " + str(author))
                    debug("release: " + str(release))
                    debug("language: " + str(language))
                    debug("imgSrc: " + str(imgSrc))
                    addLink(name=episodeTitle + " " + author + " " + release, url=subLink, mode="download", icon="", duration="",
                            desc="", genre="", lang=language)

# Alle Staffeln Holen    
def get_staffeln(id):
    debug("Hole Staffeln")
    serienpage = mainUrl + "/index.php?page=Board&boardID=" + id
    debug("get_staffeln URL:" + serienpage)
    content = getUrl(serienpage)
    content = content[content.find('<h3>Wichtige Themen</h3>') + 1:]
    content = content[:content.find('</table>')]
    linklist = []
    staffellist = []
    gefunden = 0
    spl = content.split('<div class="statusDisplayIcons">')
    for i in range(0, len(spl), 1):
        entry = spl[i]
        if "<strong>[Subs]</strong>" in entry:
            entry = entry[entry.find('<p id="threadTitl') + 1:]
            entry = entry[:entry.find('</p>')]
            match = re.compile('<a href="([^"]+)">(.+)[\ ]+-[\ ]+Staffel ([0-9]+)[^<]+</a>', re.DOTALL).findall(entry)
            for link, dummy, staffel in match:
                debug("L0RE::::: " + link + "++" + staffel + ":::::::")
                debug("suche staffel:" + video['season'] + "X")
                if video['season']:
                    # Wenn Gefunden Lsite für die Staffel alle Folgen
                    debug("YYY" + video['season'])
                    if int(staffel.strip()) == int(video['season'].strip()):
                        gefunden = 1
                        list_folgen(mainUrl + "/" + ersetze(link))
                    else:
                        staffellist.append("Staffel " + staffel)
                        linklist.append(mainUrl + "/" + ersetze(link))
                else:
                    staffellist.append("Staffel " + staffel)
                    linklist.append(ersetze(link))
                    # Wenn keine Passende Staffel gefunden
    if gefunden == 0:
        staffellist, linklist = (list(x) for x in zip(*sorted(zip(staffellist, linklist))))
        # Zeige Alle Staffeln an
        dialog = xbmcgui.Dialog()
        nr = dialog.select("subcentral.de", staffellist)
        seite = linklist[nr]
        video['season'] = staffellist[nr]
        if nr >= 0:
            list_folgen(mainUrl + "/" + seite)


# Suche
def search():
    debug("Start search")
    error = 0
    # Suche Serie
    serien_complete, ids, serien = lies_serien()
    debug("######")
    debug(serien)
    debug("######")
    show = clean_serie(video['tvshow'])
    # Wenn keine Serien Gibt es error=1 anosnten wird die ID rausgesucht
    if not show == '':
        try:
            index = serien.index(show)
            id = ids[index]
            # Hack Wenn man abbricht ist id=0, so wird nr auf 0 gesetzt
            nr = id
            debug("ID : " + str(id))
        except:
            error = 1
    else:
        error = 1
    # Wenn keine Serie gefunden
    if error == 1:
        dialog = xbmcgui.Dialog()
        nr = dialog.select("subcentral.de", serien_complete)
        id = ids[nr]
        # Nur wenn etwas ausgewählt wurde staffeln anzeigen
    if nr >= 0:
        get_staffeln(id)

    # Hole Infos uir Folge die grade läuft aus Datenbank oder Filename


def resivefile():
    currentFile = xbmc.Player().getPlayingFile()
    try:
        cf = currentFile.replace("\\", "/")
        all = cf.split("/")
        dirName = all[-2].lower()
        fileName = all[-1].lower()
        debug("Dirname: " + dirname)
        debug("Filename: " + filename)
    except:
        pass
    if video['episode'] == "":
        matchDir = re.compile('\\.s([0-9]+?)e([0-9]+?)\\.', re.DOTALL).findall(dirName)
        matchFile = re.compile('\\.s([0-9]+?)e([0-9]+?)\\.', re.DOTALL).findall(fileName)
        if len(matchDir) > 0:
            video['season'] = matchDir[0][0]
            video['episode'] = matchDir[0][1]
        elif len(matchFile) > 0:
            video['season'] = matchFile[0][0]
            video['episode'] = matchFile[0][1]
    if video['episode'] == "":
        match = re.compile('(.+?)- s(.+?)e(.+?) ', re.DOTALL).findall(xbmc.getInfoLabel('VideoPlayer.Title').lower())
        if len(match) > 0:
            video['season'] = match[0][1]
            video['episode'] = match[0][2]

    video['release'] = ""
    if "-" in fileName:
        video['release'] = (fileName.split("-")[-1]).lower()
    if "." in video['release']:
        video['release'] = video['release'][:video['release'].find(".")]
    elif "-" in dirName:
        video['release'] = (dirName.split("-")[-1]).lower()
    title = video['tvshow']
    if title == "" or video['season'] == "":
        matchDir = re.compile('(.+?)\\.s(.+?)e(.+?)\\.', re.DOTALL).findall(dirName)
        matchFile = re.compile('(.+?)\\.s(.+?)e(.+?)\\.', re.DOTALL).findall(fileName)
        matchTitle = re.compile('(.+?)- s(.+?)e(.+?) ', re.DOTALL).findall(
            xbmc.getInfoLabel('VideoPlayer.Title').lower())
        if len(matchDir) > 0:
            title = matchDir[0][0]
        elif len(matchFile) > 0:
            title = matchFile[0][0]
        elif len(matchTitle) > 0:
            title = matchTitle[0][0].strip()
        title = title.replace(".", " ")
        if "(" in title:
            title = title[:title.find("(")].strip()
    video['tvshow'] = title


# Alle Temporaeren files loeschen bevor ein neuer Untertitel Kommt
def clearSubTempDir(pfad):
    files = os.listdir(pfad)
    for file in files:
        try:
            os.remove(xbmc.translatePath(pfad + "/" + file))
        except:
            pass


# Download url to directory
def download_url(url, directory):
    headers = {'user-agent': 'Mozilla'}
    r = session.get(url, headers=headers, stream=True)
    debug("download_url status Code: " + str(r.status_code));
    if r.status_code == 403:
        xbmcgui.Dialog().notification("subcentral.de", "Username or Pw is wrong", xbmcgui.NOTIFICATION_ERROR,
                                      5000);
        addon.openSettings()
        sys.exit()
    params = cgi.parse_header(
        r.headers.get('Content-Disposition', ''))[-1]
    if 'filename' not in params:
        print('download_url Could not find a filename')
    filename = os.path.basename(params['filename'])
    abs_path = os.path.join(directory, filename)
    with open(abs_path, 'wb') as target:
        r.raw.decode_content = True
        shutil.copyfileobj(r.raw, target)
    return filename


# Neue Untertitel Holen
def setSubtitle(subUrl):
    subtitle_list = []
    filelist = []
    debug("Subtitle URL: " + subUrl)
    filename = download_url(subUrl, subdownload)
    fileLocation = subdownload + filename
    xbmcgui.Dialog().notification("subcentral.de", filename, xbmcgui.NOTIFICATION_INFO,
                                  5000);
    xbmc.executebuiltin("XBMC.Extract(" + fileLocation + ", " + subdir + ")", True)
    for file in xbmcvfs.listdir(subdir)[1]:
        filelist.append(file)
        file = os.path.join(subdir, file)
        subtitle_list.append(file)
    if len(subtitle_list) > 1:
        dialog = xbmcgui.Dialog()
        nr = dialog.select("subcentral.de", filelist)
        sub = subtitle_list[nr]
        listitem = xbmcgui.ListItem(label=sub)
    else:
        for sub in subtitle_list:
            listitem = xbmcgui.ListItem(label=sub)
    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=sub, listitem=listitem, isFolder=False)
    xbmcplugin.endOfDirectory(addon_handle)


# STARTZ
params = get_params()
getSettings()
login()
global video
video = {}
video['year'] = xbmc.getInfoLabel("VideoPlayer.Year")  # Year
video['season'] = str(xbmc.getInfoLabel("VideoPlayer.Season"))  # Season
video['episode'] = str(xbmc.getInfoLabel("VideoPlayer.Episode"))  # Episode
video['tvshow'] = xbmc.getInfoLabel("VideoPlayer.TVshowtitle")  # Show
video['title'] = xbmc.getInfoLabel("VideoPlayer.OriginalTitle")  # try to get original title
video['file_original_path'] = xbmc.Player().getPlayingFile().decode('utf-8')  # Full path of a playing file
video['3let_language'] = []  # ['scc','eng']
video['release'] = ""
PreferredSub = params.get('preferredlanguage')
if video['title'] == "":
    debug("tvshow.OriginalTitle not found")
    video['title'] = xbmc.getInfoLabel("VideoPlayer.Title")  # no original title, get just Title
# Fehlende Daten aus File
resivefile()
url = urllib.unquote_plus(params.get('url', ''))
if params['action'] == 'search':
    search()

if params['action'] == 'download':
    setSubtitle(mainUrl+"/"+url)