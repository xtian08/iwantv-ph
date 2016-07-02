import sys
import urllib
import urllib2
import json
import urlparse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from random import randint

USER_AGENT = 'okhttp/2.4.0'
SSOID = '1d3cf6ad-f133-4e22-aa15-3c9a56e4aefc'
CLIENT_ID = '4926888'
CLIENT_SECRET = '176810351025222262192664259613215154'
API_BASE_URL = 'http://cms.iwantv.com.ph'
BASIC_CREDENTIALS = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET}
LIVE_STREAM_ID = '/content/GetLiveStreams'
MODE_CATEGORY = 1
MODE_SUBCATEGORY = 2
MODE_WORLD_DETAIL = 21
MODE_EPISODE = 4
MODE_PLAY = 5
MODE_PLAY_LIVE = 6

def show_categories():
    categories = [
        {'name': 'Popular Shows', 'id': '/content/GetPopularShows', 'mode': MODE_SUBCATEGORY},
        {'name': 'Latest Episodes', 'id': '/content/GetLatestEpisodes', 'mode': MODE_SUBCATEGORY},
        {'name': 'Livestream', 'id': LIVE_STREAM_ID, 'mode': MODE_SUBCATEGORY}
    ]
    
    all_worlds = get_all_worlds_by_sso_id(0, 10)
    for world in all_worlds['DATA']:
        categories.append({'name': world['worldTitle'], 'id': world['worldID'], 'mode': MODE_WORLD_DETAIL})
    all_worlds = get_all_worlds_by_sso_id(10, 10)
    for world in all_worlds['DATA']:
        categories.append({'name': world['worldTitle'], 'id': world['worldID'], 'mode': MODE_WORLD_DETAIL})
        
    for category in categories:
        add_dir(category['name'], category['id'], category['mode'])
    xbmcplugin.endOfDirectory(this_plugin)
    
def show_subcategories(id):
    url = build_url(id)
    subcategories = get_json_response(url)
    for sub in subcategories['DATA']:
        thumb = get_program_image(sub['program_images'], 'lo')
        fanart = get_program_image(sub['program_images'], 'hi')
        # if these are the live stream sub-categories, then jump directly to play episode since live streams don't have episodes
        mode = MODE_PLAY_LIVE if id == LIVE_STREAM_ID else MODE_EPISODE
        # make these playable list items if we're dealing with live stream because
        # kodi in android doesn't honor headers piped through the URL and we just setResolvedURL down the line
        is_folder = False if id == LIVE_STREAM_ID else True
        list_properties = {'isPlayable': 'true', 'isLive': 'true'} if id == LIVE_STREAM_ID else {}
        art = {'thumb': thumb, 'fanart': fanart}
        info_labels = {'plot': sub.get('program_description')}
        add_dir(sub['program_title'], str(sub['program_id']), mode, is_folder = is_folder, art = art, list_properties = list_properties, info_labels = info_labels)
    xbmcplugin.endOfDirectory(this_plugin)
    
def show_episodes(id):
    url = build_url('/home/GetContent', params = {'program_id': id})
    episodes = get_json_response(url)
    fanart = get_program_image(episodes['DATA'][0].get('ProgramThumbnailImages'), 'large')
    program_description = episodes['DATA'][0].get('ProgramDesc')
    for episode in episodes['DATA'][0]['Episodes']:
        thumb = get_program_image(episode['EpisodeThumbnail'], 'hi')
        # set this list property as playable and not a folder and do a setResolvedURL in the method that handles playing.
        # this is they way i was able to make kodi remember the watched episodes as well as mark the elapsed time
        art = {'thumb': thumb, 'fanart': fanart}
        list_properties = {'isPlayable': 'true'}
        episode_description = episode.get('EpisodeDescription')
        plot = episode_description if episode_description else program_description
        info_labels = {'plot': plot, 'cast': filter(None, episode.get('Casts', ',').split(','))}
        add_dir(episode['EpisodeTitle'], episode['EpisodeID'], MODE_PLAY, is_folder = False, art = art, list_properties = list_properties, info_labels = info_labels)
    xbmcplugin.endOfDirectory(this_plugin)
    
def show_world_details(id):
    url = build_url('/home/GetWorldDetails', params = {'worldid': id, 'ssoid': SSOID})
    world_details = get_json_response(url)
    fanart = get_program_image(world_details['DATA'][0].get('WorldAppImage'), 'hi')
    for world in world_details['DATA'][0]['ShowData']:
        thumb = get_program_image(world['ShowThumbnailImages'], 'hi')
        info_labels = {'cast': filter(None, world.get('Casts', '').split(',')), 'plot': world.get('ShowDescription')}
        add_dir(world['ShowTitle'], world['ShowId'], MODE_EPISODE, art = {'thumb': thumb, 'fanart': fanart}, info_labels = info_labels)
    xbmcplugin.endOfDirectory(this_plugin)
    
def play_episode(name, id, thumb):
    get_iplocation()
    program_id = id if mode == MODE_PLAY_LIVE else ''
    episode_id = id if mode == MODE_PLAY else ''
    params = {'ssoid': SSOID, 'programId': program_id, 'EpisodeID': episode_id, 'IP': this_addon.getSetting('xForwardedForIp'), 'sstostage': 'PRD'}
    url = build_url('/content/ssogetasset', params = params)
    assets = get_json_response(url)
    if not assets['SUCCESS']:
        dialog = xbmcgui.Dialog()
        dialog.ok("Premium Content", assets['DATA']['ErrorMessage'])
        return
    video_type = this_addon.getSetting('liveStreamType')
    video_url = [a['VideoUrl'] for a in assets['DATA']['VideoAssets'] if a['VideoType'].lower() == video_type.lower()]
    video_url = video_url[0] if len(video_url) > 0 else ''
    liz = xbmcgui.ListItem(name)
    liz.setInfo(type="Video", infoLabels={"Title": name})
    liz.setArt({'thumb': thumb})
    video_url = '%s|X-Forwarded-For=%s' % (video_url, this_addon.getSetting('xForwardedForIp'))
    liz.setPath(video_url)
    # xbmc.Player().play would have been good for livestream but it does not honor headers piped through the URL in Android
    return xbmcplugin.setResolvedUrl(this_plugin, True, liz)
    
# trying to be legit
def get_iplocation():
    http_request(API_BASE_URL + '/Interface/GetIPLocation')
    
def get_program_image(program_images, img_dpi):
    try:
        images = [i['IMG_URL'] for i in program_images if i['IMG_DPI'] == img_dpi]
        return images[0]
    except:
        return None
    
def get_all_worlds_by_sso_id(last_row, max_count):
    url = build_url('/home/GetAllWorldsBySSOID', params = {'ssoid': SSOID, 'lastRow':  last_row, 'maxCount':  max_count})
    return get_json_response(url)
    
def build_url(path, base_url = API_BASE_URL, params = {}):
    return '{base_url}{path}?{credentials}{params}'.format(
            base_url = base_url, 
            path = path, 
            credentials = urllib.urlencode(BASIC_CREDENTIALS), 
            params = '&' + urllib.urlencode(params) if params else ''
        )
    
def http_request(url, params = {}, headers = []):
    opener = urllib2.build_opener()
    is_proxy_enabled = True if this_addon.getSetting('isProxyEnabled') == 'true' else False
    if is_proxy_enabled:
        opener = urllib2.build_opener(urllib2.ProxyHandler({'http': this_addon.getSetting('proxyAddress')}))
    if not is_x_forwarded_for_ip_valid():
        auto_generate_ip()
    headers.append(('X-Forwarded-For', this_addon.getSetting('xForwardedForIp')))
    headers.append(('User-Agent', USER_AGENT))
    opener.addheaders = headers
    if params:
        data_encoded = urllib.urlencode(params)
        response = opener.open(url, data_encoded)
    else:
        response = opener.open(url)
    return response.read()
    
def get_json_response(url):
    response = http_request(url)
    return json.loads(response)
    
def add_dir(name, id, mode, is_folder = True, **kwargs):
    query_string = {'id': id, 'mode': mode, 'name': name.encode('utf8')}
    url = '{addon_name}?{query_string}'.format(addon_name = sys.argv[0], query_string = urllib.urlencode(query_string))
    liz = xbmcgui.ListItem(name)
    info_labels = {"Title": name}
    for k, v in kwargs.iteritems():
        if not v:
            continue
        if k == 'info_labels':
            info_labels = dict(info_labels.items() + v.items())
        if k == 'list_properties':
            for list_property_key, list_property_value in v.iteritems():
                liz.setProperty(list_property_key, list_property_value)
        if k == 'art':
            liz.setArt(v)
            url = '{url}&{art_params}'.format(url = url, art_params = urllib.urlencode(v))
    liz.setInfo(type = "Video", infoLabels = info_labels)
    return xbmcplugin.addDirectoryItem(handle = this_plugin, url = url, listitem = liz, isFolder = is_folder)

def is_x_forwarded_for_ip_valid():
    x_forwarded_for_ip = xbmcaddon.Addon().getSetting('xForwardedForIp').strip()
    if x_forwarded_for_ip == '0.0.0.0' or x_forwarded_for_ip == '':
        return False
    return True
    
def auto_generate_ip():
    ip_range_list = [
        (1848401920, 1848406015),
        (1884172288, 1884176383),
        (1931427840, 1931431935),
        (2000617472, 2000621567),
        (2070704128, 2070708223),
    ]

    start_ip_number, end_ip_number = ip_range_list[randint(0, len(ip_range_list) - 1)]
    ip_number = randint(start_ip_number, end_ip_number)
    w = (ip_number / 16777216) % 256
    x = (ip_number / 65536) % 256
    y = (ip_number / 256) % 256
    z = (ip_number) % 256
    if z == 0: z = 1
    if z == 255: z = 254
    ip_address = '%s.%s.%s.%s' % (w, x, y, z)
    xbmcaddon.Addon().setSetting('xForwardedForIp', ip_address)
    
def try_get_param(params, name, default_value = None):
    return params[name][0] if name in params else default_value
    
def show_message(message, title = xbmcaddon.Addon().getLocalizedString(50701)):
    if not message:
        return
    xbmc.executebuiltin("ActivateWindow(%d)" % (10147, ))
    win = xbmcgui.Window(10147)
    xbmc.sleep(100)
    win.getControl(1).setLabel(title)
    win.getControl(5).setText(message)
    
this_addon = xbmcaddon.Addon()
mode = MODE_CATEGORY
this_plugin = int(sys.argv[1])
params = urlparse.parse_qs(sys.argv[2].replace('?',''))
name = try_get_param(params, 'name')
mode= int(try_get_param(params, 'mode', mode))
thumb = try_get_param(params, 'thumb', '')
id = try_get_param(params, 'id')

if mode == MODE_CATEGORY or not id or len(id) == 0:
    show_categories()
elif mode == MODE_SUBCATEGORY:
    show_subcategories(id)
elif mode == MODE_EPISODE:
    show_episodes(id)
elif mode == MODE_PLAY or mode == MODE_PLAY_LIVE:
    play_episode(name, id, thumb)
elif mode == MODE_WORLD_DETAIL:
    show_world_details(id)
    
if this_addon.getSetting('announcement') != this_addon.getAddonInfo('version'):
    messages = {
        '1.0.0': 'Your iWantv addon has been updated.\n\nThe addon now remembers where you left off on your favorite teleserye plus lots of other improvements. Enjoy watching!'
        }
    if this_addon.getAddonInfo('version') in messages:
        show_message(messages[this_addon.getAddonInfo('version')], xbmcaddon.Addon().getLocalizedString(50701))
        xbmcaddon.Addon().setSetting('announcement', this_addon.getAddonInfo('version'))

