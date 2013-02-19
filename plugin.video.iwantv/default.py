import sys, urllib, urllib2, json, cookielib, time, os.path, hashlib
import xbmc, xbmcgui, xbmcplugin, xbmcaddon
from lib.SimpleCache import SimpleCache

import CommonFunctions
common = CommonFunctions
common.plugin = xbmcaddon.Addon().getAddonInfo('name')

# common.dbg = True # Default
# common.dbglevel = 3 # Default

def showCategories():
    accountChanged = checkAccountChange()
    if accountChanged:
        cleanCache(True)
    else:
        cleanCache(False)
    categories = [
        { 'name' : 'TV', 'url' : '/TV/Categories/1', 'mode' : 1 },
        { 'name' : 'Movies', 'url' : '/Movies/Categories/2', 'mode' : 1 },
        { 'name' : 'Others', 'url' : '/TV/Categories/3', 'mode' : 1 },
    ]
    for c in categories:
        addDir(c['name'], c['url'], c['mode'], 'icon.png')
    return True

def showSubCategories(url):
    subCatList = getFromCache(url)
    if subCatList == None:
        htmlData = callServiceApi(url)
        subCatOuterHtml = common.parseDOM(htmlData, "ul", attrs = {'class' : 'movie-categories-list'})
        subCatList = common.parseDOM(subCatOuterHtml[0], "li", ret = 'name')
        setToCache(url, subCatList)
    typeId = url[-1:]
    for s in subCatList:
        addDir(s, r'{"TypeID":%s,"GenreID":"%s"}' % (typeId, s), 2, 'icon.png')
    return True
        
def showShows(url):
    htmlData = ''
    showsHtml = []
    cacheKey = url
    headers = [('Content-type', 'application/x-www-form-urlencoded'), ('X-Requested-With', 'XMLHttpRequest')]
    params = json.loads(url)
    for i in range(int(xbmcplugin.getSetting(thisPlugin,'loginRetries')) + 1):
        showsHtml = getFromCache(cacheKey)
        if showsHtml == None or len(showsHtml) == 0:
            htmlData = callServiceApi('/Viewmore/GetList', params, headers)
            showsHtml = common.parseDOM(htmlData, "li")
            setToCache(cacheKey, showsHtml)
        if len(showsHtml) > 0:
            break
        else:
            login()
    hasShows = False
    for showInfo in showsHtml:
        if len(showInfo.strip()) > 0:
            hasShows = True
            spanTitle = common.parseDOM(showInfo, "span", attrs = {'class' : 'video-title'})
            showTitle = common.parseDOM(spanTitle[0], "a")
            showUrl = common.parseDOM(spanTitle[0], "a" , ret = 'href')
            showThumbnail = common.parseDOM(showInfo, "img" , ret = 'src')
            if params['TypeID'] == 2 or params['TypeID'] == 3:
                addDir(showTitle[0].encode('utf8'), showUrl[0], 4, showThumbnail[0])
            else:
                addDir(showTitle[0].encode('utf8'), showUrl[0], 3, showThumbnail[0])
    if hasShows == False:
        dialog = xbmcgui.Dialog()
        dialog.ok("No Shows", "No shows found.")
    return hasShows
        
def showEpisodes(url):
    url = urllib.quote(url)
    episodesHtml = []
    htmlData = ''
    for i in range(int(xbmcplugin.getSetting(thisPlugin,'loginRetries')) + 1):
        episodesHtml = getFromCache(url)
        if episodesHtml == None:
            htmlData = callServiceApi(url)
            episodesHtml = common.parseDOM(htmlData, "div", attrs = { 'class' : 'video-other-episode'})
        if len(episodesHtml) == 0:
            login()
        else:
            setToCache(url, episodesHtml)
            break
    
    if len(episodesHtml) == 0:
        videoPageHtml = common.parseDOM(htmlData, "div", attrs = { 'class' : 'video-page-player'})
        if len(videoPageHtml) > 0:
            if videoPageHtml[0].find('noaccess()'):
                dialog = xbmcgui.Dialog()
                dialog.ok("Incorrect Login", "Please check your email and password.")
                return False
    else:
        if episodesHtml[0].find('Other Channels') >= 0:
            return False
    episodesListHtml = common.parseDOM(episodesHtml[0], "li")
    for e in episodesListHtml:
        title = common.parseDOM(e, "span", attrs = { 'class' : 'video-adate'})
        url = common.parseDOM(e, "a", attrs = { 'class' : 'btn-play-blue playbtn'}, ret = 'href')
        thumbnail = common.parseDOM(e, "img", ret = 'src')
        if len(thumbnail) <= 0:
            addDir(title[0], url[0], 4, '')
        else:
            addDir(title[0], url[0], 4, thumbnail[0])
    return True
        
def playEpisode(url):
    url = urllib.quote(url)
    errorCode = -1
    htmlData = ''
    videoHint = None
    playerKey = None
    playerID = None
    linkBaseURL = None
    videoPlayer = None
    episodeDetails = {}
    for i in range(int(xbmcplugin.getSetting(thisPlugin,'loginRetries')) + 1):
        htmlData = callServiceApi(url)
        videoHint = common.parseDOM(htmlData, "div", attrs = {'class' : 'video-page-player'})
        playerKey = common.parseDOM(htmlData, "param", attrs = {'name' : 'playerKey'}, ret = 'value')
        playerID = common.parseDOM(htmlData, "param", attrs = {'name' : 'playerID'}, ret = 'value')
        linkBaseURL = common.parseDOM(htmlData, "param", attrs = {'name' : 'linkBaseURL'}, ret = 'value')
        videoPlayer = common.parseDOM(htmlData, "param", attrs = {'name' : '@videoPlayer'}, ret = 'value')
        if videoHint and playerKey and playerID and linkBaseURL and videoPlayer:
            break
        else:
            login()
    if len(playerKey) == 0 or len(playerID) == 0:
        if len(videoHint) > 0:
            if videoHint[0].find('npu-step1-box'):
                dialog = xbmcgui.Dialog()
                dialog.ok("Premium Content", "You need a premium account to access this item.", 'You can upgrade your subscription via the iWantv website.')
                return False
    from lib.brightcove import BrightCove
    brightCove = BrightCove(brightCoveToken, playerKey[0], playerID[0])
    xForwardedForIp = xbmcplugin.getSetting(thisPlugin,'xForwardedForIp')
    headers = [('X-Forwarded-For', xForwardedForIp)]
    brightCoveData = brightCove.getBrightCoveData(linkBaseURL[0], videoPlayer[0].replace('ref:', ''), userAgent, **{'headers' : headers})
    videoUrl = brightCoveData['programmedContent']['videoPlayer']['mediaDTO']['FLVFullLengthURL']
    import re
    pattern = re.compile(r'/ondemand/&(mp4:.+\.mp4)\?')
    m = pattern.search(videoUrl)
    playPath = m.group(1)
    liz=xbmcgui.ListItem(name, iconImage = "DefaultVideo.png", thumbnailImage = thumbnail)
    liz.setInfo( type="Video", infoLabels = { "Title": name } )
    liz.setProperty('app', 'ondemand')
    liz.setProperty('PlayPath', playPath)
    videoUrl = videoUrl.replace('/ondemand/&mp4', '/ondemand/mp4')
    xbmc.Player().play(videoUrl, liz)
    return False

def callServiceApi(path, params = {}, headers = []):
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookieJar))
    headers.append(('User-Agent', userAgent))
    opener.addheaders = headers
    if params:
        data_encoded = urllib.urlencode(params)
        response = opener.open(baseUrl + path, data_encoded)
    else:
        response = opener.open(baseUrl + path)
    return response.read()

def login():
    cookieJar.clear()
    emailAddress = xbmcplugin.getSetting(thisPlugin,'emailAddress')
    password = xbmcplugin.getSetting(thisPlugin,'password')
    formdata = { "email" : emailAddress, "password": password }
    callServiceApi("/Account/UserLoginAjax", formdata)
    
def checkAccountChange():
    emailAddress = xbmcplugin.getSetting(thisPlugin,'emailAddress')
    password = xbmcplugin.getSetting(thisPlugin,'password')
    hash = hashlib.sha1(emailAddress + password).hexdigest()
    hashFile = os.path.join(xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('profile')), 'a.tmp')
    savedHash = ''
    accountChanged = False
    if os.path.exists(hashFile):
        with open(hashFile) as f:
            savedHash = f.read()
    if savedHash != hash:
        login()
        accountChanged = True
    if os.path.exists(xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))):
        with open(hashFile, 'w') as f:
            f.write(hash)
    return accountChanged

def getFromCache(key):
    try:
        if isCacheEnabled:
            cacheKey = hashlib.sha1(key).hexdigest()
            return SimpleCache(cacheExpirySeconds).get(cacheKey)
        else:
            return None
    except:
        return None

def setToCache(key, value):
    try:
        if isCacheEnabled:
            cacheKey = hashlib.sha1(key).hexdigest()
            SimpleCache(cacheExpirySeconds).set(cacheKey, value)
    except:
        pass

def cleanCache(force = False):
    try:
        if isCacheEnabled:
            purgeAfterSeconds = int(xbmcplugin.getSetting(thisPlugin,'purgeAfterDays')) * 24 * 60 * 60
            if force:
                purgeAfterSeconds = 0
            return SimpleCache(cacheExpirySeconds).cleanCache(purgeAfterSeconds)
        else:
            return None
    except:
        return None
    
def getParams():
    param={}
    paramstring=sys.argv[2]
    if len(paramstring)>=2:
            params=sys.argv[2]
            cleanedparams=params.replace('?','')
            if (params[len(params)-1]=='/'):
                    params=params[0:len(params)-2]
            pairsofparams=cleanedparams.split('&')
            param={}
            for i in range(len(pairsofparams)):
                    splitparams={}
                    splitparams=pairsofparams[i].split('=')
                    if (len(splitparams))==2:
                            param[splitparams[0]]=splitparams[1]
    return param

def addLink(name,url,title,iconimage):
    liz=xbmcgui.ListItem(name, iconImage="DefaultVideo.png", thumbnailImage=iconimage)
    liz.setInfo( type="Video", infoLabels={ "Title": title } )
    return xbmcplugin.addDirectoryItem(handle=thisPlugin,url=url,listitem=liz)

def addDir(name, url, mode, thumbnail, page = 1):
    u=sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)+"&page="+str(page)+"&thumbnail="+urllib.quote_plus(thumbnail)
    liz=xbmcgui.ListItem(name, iconImage="DefaultFolder.png", thumbnailImage=thumbnail)
    liz.setInfo( type="Video", infoLabels={ "Title": name } )
    return xbmcplugin.addDirectoryItem(handle=thisPlugin,url=u,listitem=liz,isFolder=True)


thisPlugin = int(sys.argv[1])
userAgent = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:18.0) Gecko/20100101 Firefox/18.0'
baseUrl = 'http://www.iwantv.com.ph'
cookieJarType = ''
cookieJar = cookielib.CookieJar()
if os.path.exists(xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))):
    cookieFile = os.path.join(xbmc.translatePath(xbmcaddon.Addon().getAddonInfo('profile')), 'iwantv.cookie')
    cookieJar = cookielib.LWPCookieJar(cookieFile)
    cookieJarType = 'LWPCookieJar'

if cookieJarType == 'LWPCookieJar':
    try:
        cookieJar.load()
    except:
        login()
# login()

params=getParams()
url=None
name=None
mode=None
page=1
thumbnail = ''
brightCoveToken = 'f9c60da6432f7642249592a9d2669046515cb302'
cacheExpirySeconds = int(xbmcplugin.getSetting(thisPlugin,'cacheHours')) * 60 * 60
isCacheEnabled = True if xbmcplugin.getSetting(thisPlugin,'isCacheEnabled') == 'true' else False


try:
    url=urllib.unquote_plus(params["url"])
except:
    pass
try:
    name=urllib.unquote_plus(params["name"])
except:
    pass
try:
    mode=int(params["mode"])
except:
    pass
try:
    page=int(params["page"])
except:
    pass
try:
    thumbnail=urllib.unquote_plus(params["thumbnail"])
except:
    pass
    
success = False
if mode == None or url == None or len(url) < 1:
    success = showCategories()
elif mode == 1:
    success = showSubCategories(url)
elif mode == 2:
    success = showShows(url)
elif mode == 3:
    success = showEpisodes(url)
elif mode == 4:
    success = playEpisode(url)
elif mode == 10:
    success = showSubscribedCategories(url)
elif mode == 11:
    success = showSubscribedShows(url)

if success == True:
    xbmcplugin.endOfDirectory(thisPlugin)


if cookieJarType == 'LWPCookieJar':
    cookieJar.save()
