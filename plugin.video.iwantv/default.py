import sys, urllib, urllib2, json, cookielib, time, os.path, hashlib
import xbmc, xbmcgui, xbmcplugin, xbmcaddon
from lib.SimpleCache import SimpleCache

import CommonFunctions
common = CommonFunctions
thisAddon = xbmcaddon.Addon()
common.plugin = thisAddon.getAddonInfo('name')

# common.dbg = True # Default
# common.dbglevel = 3 # Default

def showCategories():
    accountChanged = checkAccountChange()
    if not isXForwardedForIpValid():
        autoGenerateIp()
    if accountChanged:
        cleanCache(True)
    else:
        cleanCache(False)
    categories = [
        { 'name' : 'TV', 'url' : '/TV/Categories/1', 'mode' : 1 },
        { 'name' : 'Movies', 'url' : '/Movies/Categories/2', 'mode' : 1 },
        { 'name' : 'Live', 'url' : '/TV/Channel/3', 'mode' : 1 },
    ]
    for c in categories:
        addDir(c['name'], c['url'], c['mode'], 'icon.png')
    xbmcplugin.endOfDirectory(thisPlugin)

def getSubCategories(url, htmlData):
    subCatListKey = 'subcatlist:v1:' + url
    subCatList = getFromCache(subCatListKey)
    if subCatList == None:
        subCatOuterHtml = common.parseDOM(htmlData, "ul", attrs = {'class' : 'movie-categories-list'})
        subCatList = common.parseDOM(subCatOuterHtml[0], "li", ret = 'name')
        setToCache(subCatListKey, subCatList)
    return subCatList

def getLiveChannelDetails(url, htmlData):
    liveChannelDetailsKey = '%s:chaneldetails:v2' % url
    liveChannelDetails = getFromCache(liveChannelDetailsKey)
    if liveChannelDetails == None:
        liveChannelDetails = {}
        subCatOuterHtml = common.parseDOM(htmlData, "ul", attrs = {'class' : 'movie-categories-list'})
        groupIds = common.parseDOM(subCatOuterHtml[0], "li", ret = 'groupid')
        for groupId in groupIds:
            channelName = common.parseDOM(subCatOuterHtml[0], "li", attrs = { 'groupid' : groupId }, ret = 'name')
            channelDetailsHtml = common.parseDOM(subCatOuterHtml[0], "li", attrs = { 'groupid' : groupId })
            imgUrl = common.parseDOM(channelDetailsHtml[0], "img", ret = 'src')
            liveChannelDetails[channelName[0]] = (r'{ "groupid" : %s, "day" : "Sunday" }' % groupId, imgUrl[0])
        setToCache(liveChannelDetailsKey, liveChannelDetails)
    return liveChannelDetails
    
def showSubCategories(url):
    htmlDataCacheKey = 'html:v1:' + url
    htmlData = getFromCache(htmlDataCacheKey)
    if htmlData == None:
        htmlData = callServiceApi(url)
    subCatList = getSubCategories(url, htmlData)
    if url == liveShowsPath:
        liveChannelDetails = getLiveChannelDetails(url, htmlData)
        for k, v in liveChannelDetails.iteritems():
            addDir(k, v[0], 5, v[1], isFolder = False, **{ 'listProperties' : { 'IsPlayable' : 'true' } })
    else:
        typeId = url[-1:]
        for s in subCatList:
            addDir(s, r'{"TypeID":%s,"GenreID":"%s"}' % (typeId, s), 2, '')
    xbmcplugin.endOfDirectory(thisPlugin)
        
def showShows(url):
    htmlData = ''
    showsHtml = []
    cacheKey = url
    headers = [('Content-type', 'application/x-www-form-urlencoded'), ('X-Requested-With', 'XMLHttpRequest')]
    params = json.loads(url)
    for i in range(int(thisAddon.getSetting('loginRetries')) + 1):
        showsHtml = getFromCache(cacheKey)
        if showsHtml == None or len(showsHtml) == 0:
            htmlData = callServiceApi('/Viewmore/GetList', params, headers)
            if htmlData.find(r'</li>') == -1:
                import re
                htmlData = re.sub(r"(<span class='video-ep'>.+?</span>)", r'\1</div></li>', htmlData)
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
                addDir(showTitle[0].encode('utf8'), showUrl[0], 4, showThumbnail[0], isFolder = False, **{ 'listProperties' : { 'IsPlayable' : 'true' } })
            else:
                addDir(showTitle[0].encode('utf8'), showUrl[0], 3, showThumbnail[0])
    if hasShows == False:
        dialog = xbmcgui.Dialog()
        dialog.ok("No Shows", "No shows found.")
    else:
        xbmcplugin.endOfDirectory(thisPlugin)
        
def showEpisodes(url):
    url = urllib.quote(url)
    episodesHtml = []
    htmlData = ''
    for i in range(int(thisAddon.getSetting('loginRetries')) + 1):
        #episodesHtml = getFromCache(url)
        #if episodesHtml == None:
        htmlData = callServiceApi(url)
        episodesHtml = common.parseDOM(htmlData, "div", attrs = { 'class' : 'video-other-episode'})
        if len(episodesHtml) == 0:
            login()
        else:
            #setToCache(url, episodesHtml)
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
        kwargs = { 'listProperties' : { 'IsPlayable' : 'true' } }
        if len(thumbnail) <= 0:
            addDir(title[0], url[0], 4, '', isFolder = False, **kwargs)
        else:
            addDir(title[0], url[0], 4, thumbnail[0], isFolder = False, **kwargs)
    xbmcplugin.endOfDirectory(thisPlugin)

def getPlayUrl(jsonParams):
    params = json.loads(jsonParams)
    programHtml = callServiceApi('/Home/GetChannelLiveList', params )
    channelUrl = common.parseDOM(programHtml, "a", attrs = { 'class' : 'sched-prog' }, ret = 'href')
    return channelUrl[0]
    
def getQualityVideoUrl(renditions, iosRenditions):
    videoQuality = int(thisAddon.getSetting('videoQuality'))
    videoRenditionType = thisAddon.getSetting('videoRenditionType')
    liveStreamType = thisAddon.getSetting('liveStreamType')
    videoRenditions = []
    videoUrl = None
    allRenditions = iosRenditions
    allRenditions.extend(renditions)
    liveStreams = [r for r in allRenditions if r['size'] <= 0]
    if liveStreams:
        if liveStreamType.upper() == 'HLS':
            return [s for s in liveStreams if s['defaultURL'].find('m3u8') > -1][0]['defaultURL']
        else:
            return [s for s in liveStreams if s['defaultURL'].find('m3u8') <= -1][0]['defaultURL']
    if videoRenditionType.upper() == 'MOBILE' and iosRenditions is not None:
        videoRenditions = iosRenditions
    elif videoRenditionType.upper() == 'DESKTOP' and renditions is not None:
        videoRenditions = renditions
    if not videoRenditions:
        # fallback, use available renditions
        videoRenditions = allRenditions
    
    videoEncodings = {}
    for v in videoRenditions:
        videoEncodings[v['encodingRate']] = v['defaultURL']
    sortedEncodingRates = sorted(videoEncodings.keys())
    if videoQuality == 2: # high
        return videoEncodings[max(sortedEncodingRates)]
    elif videoQuality == 0: #low
        return videoEncodings[min(sortedEncodingRates)]
    else: # medium
        # we'll consider the next one from the highest encoding as medium
        if len(sortedEncodingRates) > 1:
            sortedEncodingRates.remove(max(sortedEncodingRates))
            return videoEncodings[max(sortedEncodingRates)]
        else:
            return videoEncodings[max(sortedEncodingRates)]
    
def getVideoUrl(videoBaseUrl, brightCoveToken, playerKey, playerId, videoPlayer, isMyExperience, publisherId):
    from lib.brightcove import BrightCove
    isXfwdForEnabled = True if thisAddon.getSetting('isXfwdForEnabled') == 'true' else False
    kwargs = {}
    headers = []
    if isXfwdForEnabled:
        if not isXForwardedForIpValid():
            autoGenerateIp()
        headers = [('X-Forwarded-For', thisAddon.getSetting('xForwardedForIp'))]
        kwargs = {'headers' : headers }
    isProxyEnabled = True if thisAddon.getSetting('isProxyEnabled') == 'true' else False
    if isProxyEnabled:
        kwargs['proxy'] = thisAddon.getSetting('proxyAddress')
    brightCoveData = None
    isSafeNetworkBypass = True if thisAddon.getSetting('isSafeNetworkBypass') == 'true' else False
    defaultVideoUrl = ''
    renditions = []
    iosRenditions = []
    videoRenditions = None
    if isSafeNetworkBypass:
        brightCove = BrightCove(brightCoveToken, playerKey, int(playerId))
        if videoPlayer.startswith('ref:'):
            brightCoveData = brightCove.findMediaByReferenceId(int(playerId), videoPlayer.replace('ref:', ''), publisherId, userAgent = userAgent, **kwargs)
        else:
            brightCoveData = brightCove.findMediaById(int(playerId), videoPlayer.replace('ref:', ''), publisherId, userAgent = userAgent, **kwargs)
        defaultVideoUrl = brightCoveData['FLVFullLengthURL']
        renditions = brightCoveData['renditions']
        iosRenditions = brightCoveData['IOSRenditions']
    else:
        brightCove = BrightCove(brightCoveToken, playerKey, int(playerId))
        if isMyExperience:
            brightCoveData = brightCove.getBrightCoveData(videoBaseUrl, videoPlayer.replace('ref:', ''), userAgent, **kwargs)
        else:
            brightCoveData = brightCove.getBrightCoveData(videoBaseUrl, contentRefId = None, contentId = videoPlayer, userAgent = userAgent, **kwargs)
        defaultVideoUrl = brightCoveData['programmedContent']['videoPlayer']['mediaDTO']['FLVFullLengthURL']
        renditions = brightCoveData['programmedContent']['videoPlayer']['mediaDTO']['renditions']
        iosRenditions = brightCoveData['programmedContent']['videoPlayer']['mediaDTO']['IOSRenditions']
    videoUrl = getQualityVideoUrl(renditions, iosRenditions)
    if videoUrl is None:
        videoUrl = defaultVideoUrl
    return videoUrl

def playEpisode(url, mode):
    if mode == 5:
        url = getPlayUrl(url)
    url = urllib.quote(url)
    errorCode = -1
    htmlData = ''
    videoHint = None
    playerKey = None
    playerID = None
    linkBaseURL = None
    videoPlayer = None
    episodeDetails = {}
    for i in range(int(thisAddon.getSetting('loginRetries')) + 1):
        htmlData = callServiceApi(url)
        videoHint = common.parseDOM(htmlData, "div", attrs = {'class' : 'video-page-player'})
        playerKey = common.parseDOM(htmlData, "param", attrs = {'name' : 'playerKey'}, ret = 'value')
        playerID = common.parseDOM(htmlData, "param", attrs = {'name' : 'playerID'}, ret = 'value')
        linkBaseURL = common.parseDOM(htmlData, "param", attrs = {'name' : 'linkBaseURL'}, ret = 'value')
        videoPlayer = common.parseDOM(htmlData, "param", attrs = {'name' : '@videoPlayer'}, ret = 'value')
        myExperience = common.parseDOM(htmlData, "object", attrs = {'class' : 'BrightcoveExperience'}, ret = 'id')
        if videoHint and playerKey and playerID and videoPlayer:
            break
        else:
            login()
    if len(playerKey) == 0 or len(playerID) == 0:
        if len(videoHint) > 0:
            if videoHint[0].find('npu-step1-box'):
                dialog = xbmcgui.Dialog()
                dialog.ok("Premium Content", "You need a premium account to access this item.", 'You can upgrade your subscription via the iWantv website.')
                return False
    videoBaseUrl = ''
    if len(linkBaseURL) > 0:
        videoBaseUrl = linkBaseURL[0]
    else:
        videoBaseUrl = baseUrl + url
    isMyExperience = False
    if len(myExperience) > 0 and myExperience[0] == 'myExperience':
        isMyExperience = True
    videoUrl = getVideoUrl(videoBaseUrl, brightCoveToken, playerKey[0], playerID[0], videoPlayer[0], isMyExperience, publisherId)
    liz=xbmcgui.ListItem(name, iconImage = "DefaultVideo.png", thumbnailImage = thumbnail)
    liz.setInfo( type="Video", infoLabels = { "Title": name } )
    if 'm3u8' in videoUrl:
        pass
    elif videoUrl.startswith('rtmp'):
        pass
        import re
        pattern = ''
        app = ''
        if r'/ondemand/' in videoUrl:
            app = 'ondemand'
            pattern = re.compile(r'/ondemand/&(mp4:.+\.mp4)')
        else:
            app = 'live'
            pattern = re.compile(r'/live/&(.+)')
        m = pattern.search(videoUrl)
        playPath = ''
        if m:
            playPath = m.group(1)
        if app == 'ondemand':
            videoUrl = videoUrl.replace('/ondemand/&mp4', '/ondemand/mp4')
        if app == 'live':
            #liz.setProperty('live', '1')
            videoUrl = videoUrl + ' live=1 app=live playPath=' + playPath + ' swfUrl=' + 'http://admin.brightcove.com/viewer/us20130222.1010/BrightcoveBootloader.swf'
            
        liz.setProperty('app', app)
        liz.setProperty('PlayPath', playPath)
        liz.setProperty('IsPlayable', 'true')
    else:
        pass
    liz.setPath(videoUrl)
    return xbmcplugin.setResolvedUrl(thisPlugin, True, liz)

def callServiceApi(path, params = {}, headers = [], opener = None):
    if opener == None:
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookieJar))
        #opener = urllib2.build_opener(urllib2.ProxyHandler({'http': '127.0.0.1:8888'}), urllib2.HTTPCookieProcessor(cookieJar))
    else:
        urllib2.install_opener(opener)
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
    emailAddress = thisAddon.getSetting('emailAddress')
    password = thisAddon.getSetting('password')
    formdata = { "loginID" : emailAddress, "password": password }
    callServiceApi("/Account/UserLoginAjax", formdata)
    cookieJar.save(ignore_discard = True, ignore_expires = True)
    
def checkAccountChange():
    emailAddress = thisAddon.getSetting('emailAddress')
    password = thisAddon.getSetting('password')
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

def isXForwardedForIpValid():
    xForwardedForIp = xbmcaddon.Addon().getSetting('xForwardedForIp').strip()
    if xForwardedForIp == '0.0.0.0' or xForwardedForIp == '':
        return False
    return True
    
def autoGenerateIp():
    ipRanges = [
        (1848401920, 1848406015),
        (1884172288, 1884176383),
        (1931427840, 1931431935),
        (2000617472, 2000621567),
        (2070704128, 2070708223),
    ]
    from random import randint
    startIpNumber, endIpNumber = ipRanges[randint(0, len(ipRanges) - 1)]
    ipNumber = randint(startIpNumber, endIpNumber)
    w = (ipNumber / 16777216) % 256
    x = (ipNumber / 65536) % 256
    y = (ipNumber / 256) % 256
    z = (ipNumber) % 256
    if z == 0: z = 1
    if z == 255: z = 254
    ipAddress = '%s.%s.%s.%s' % (w, x, y, z)
    xbmcaddon.Addon().setSetting('xForwardedForIp', ipAddress)
    
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
            purgeAfterSeconds = int(thisAddon.getSetting('purgeAfterDays')) * 24 * 60 * 60
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

def addDir(name, url, mode, thumbnail, page = 1, isFolder = True, **kwargs):
    u=sys.argv[0]+"?url="+urllib.quote_plus(url)+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)+"&page="+str(page)+"&thumbnail="+urllib.quote_plus(thumbnail)
    liz=xbmcgui.ListItem(name, iconImage="DefaultFolder.png", thumbnailImage=thumbnail)
    liz.setInfo( type="Video", infoLabels={ "Title": name } )
    for k, v in kwargs.iteritems():
        if k == 'listProperties':
            for listPropertyKey, listPropertyValue in v.iteritems():
                liz.setProperty(listPropertyKey, listPropertyValue)
    return xbmcplugin.addDirectoryItem(handle=thisPlugin,url=u,listitem=liz,isFolder=isFolder)


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
        cookieJar.load(ignore_discard = True, ignore_expires = True)
    except:
        login()
else:
    login()

params=getParams()
url=None
name=None
mode=None
page=1
thumbnail = ''
brightCoveToken = 'f9c60da6432f7642249592a9d2669046515cb302'
publisherId = 1213020456001
cacheExpirySeconds = int(thisAddon.getSetting('cacheHours')) * 60 * 60
isCacheEnabled = True if thisAddon.getSetting('isCacheEnabled') == 'true' else False
liveShowsPath = '/TV/Channel/3'

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
    
if mode == None or url == None or len(url) < 1:
    showCategories()
elif mode == 1:
    showSubCategories(url)
elif mode == 2:
    showShows(url)
elif mode == 3:
    showEpisodes(url)
elif mode == 4 or mode == 5:
    playEpisode(url, mode)
elif mode == 10:
    showSubscribedCategories(url)
elif mode == 11:
    showSubscribedShows(url)

