import os.path
import sys
import pickle
import hashlib
import traceback
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
CLIENT_ID = '4926888'
CLIENT_SECRET = '176810351025222262192664259613215154'
API_BASE_URL = 'http://cms.iwantv.com.ph'
LOGIN_BASE_URL = 'http://accounts.abs-cbn.com'
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
        title = world['worldTitle'] if is_subscribed(world.get('Tiers')) else '[I]{0}[/I]'.format(world['worldTitle'])
        categories.append({'name': title, 'id': world['worldID'], 'mode': MODE_WORLD_DETAIL})
    all_worlds = get_all_worlds_by_sso_id(10, 10)
    for world in all_worlds['DATA']:
        title = world['worldTitle'] if is_subscribed(world.get('Tiers')) else '[I]{0}[/I]'.format(world['worldTitle'])
        categories.append({'name': title, 'id': world['worldID'], 'mode': MODE_WORLD_DETAIL})
        
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
        art = {'thumb': thumb, 'fanart': fanart}
        info_labels = {'plot': sub.get('program_description')}
        title = sub['program_title'] if is_subscribed(sub.get('Tiers')) else '[I]{0}[/I]'.format(sub['program_title'])
        add_dir(title, str(sub['program_id']), mode, art = art, info_labels = info_labels)
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
    sso_id = user_data['sso_id']
    if not sso_id:
        return
    url = build_url('/home/GetWorldDetails', params = {'worldid': id, 'ssoid': sso_id})
    world_details = get_json_response(url)
    fanart = get_program_image(world_details['DATA'][0].get('WorldAppImage'), 'hi')
    for world in world_details['DATA'][0]['ShowData']:
        thumb = get_program_image(world['ShowThumbnailImages'], 'hi')
        info_labels = {'cast': filter(None, world.get('Casts', '').split(',')), 'plot': world.get('ShowDescription')}
        title = world['ShowTitle'] if is_subscribed(world.get('Tiers')) else '[I]{0}[/I]'.format(world['ShowTitle'])
        add_dir(title, world['ShowId'], MODE_EPISODE, art = {'thumb': thumb, 'fanart': fanart}, info_labels = info_labels)
    xbmcplugin.endOfDirectory(this_plugin)
    
def play_episode(name, id, thumb):
    get_iplocation()
    program_id = id if mode == MODE_PLAY_LIVE else ''
    episode_id = id if mode == MODE_PLAY else ''
    sso_id = user_data['sso_id']
    if not sso_id:
        return
    params = {'ssoid': sso_id, 'programId': program_id, 'EpisodeID': episode_id, 'IP': this_addon.getSetting('xForwardedForIp'), 'sstostage': 'PRD'}
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
    if mode == MODE_PLAY_LIVE:
        xbmc.Player().play(item = video_url, listitem = liz)
    else:
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
        
def is_subscribed(tiers):
    subscribed = True
    try:
        # just assume that we are subscribed
        xbmc.log('asdfadfadf' + str(tiers))
        if not tiers:
            return True
        program_package_ids = [int(t['Key']) for t in tiers]
        subscribed_ids = [i for i in program_package_ids if i in user_data['package_ids']]
        subscribed = len(subscribed_ids) > 0
    except:
        xbmc.log(traceback.format_exc())
    return subscribed
        
def get_account_hash():
    email_address = this_addon.getSetting('emailAddress')
    password = this_addon.getSetting('password')
    return hashlib.sha1(email_address + password).hexdigest()
    
def has_required_properties(data):
    return data.get('account_hash') == get_account_hash() and data.get('sso_id') and data.has_key('package_ids')
    
def get_user_data(user_file):
    data = {}
    try:
        data = read_user_file(user_file)
        account_hash = data.get('account_hash')
        if not has_required_properties(data):
            data = get_new_user_data()
            write_user_file(user_file, data)
    except:
        xbmc.log(traceback.format_exc())
    return data
    
def read_user_file(user_file):
    with open(user_file, 'rb') as f:
        return pickle.load(f)
        
def write_user_file(user_file, data):
    with open(user_file, 'wb') as f:
        pickle.dump(data, f)
        
def get_new_user_data():
    sso_id = get_new_sso_id()
    package_ids = get_new_package_ids(sso_id)
    account_hash = get_account_hash()
    return {'account_hash': account_hash, 'sso_id': sso_id, 'package_ids': package_ids}
        
def get_new_sso_id():
    sso_id = None
    try:
        url = build_url('/api/oauth/accessTokenSSO', base_url = LOGIN_BASE_URL, params = {'_urlRefferer': 'com.abs-cbn.iwanttv'})
        access_data = get_json_response(url, params = {'a': ''})
        url = build_url('/api/iwantv/Login', base_url = LOGIN_BASE_URL, params = {'access_token': access_data.get('access_token'), 'device': 'app'})
        email_address = this_addon.getSetting('emailAddress')
        password = this_addon.getSetting('password')
        login_data = get_json_response(url, params = {'loginID': email_address, 'password': password})
        if not login_data.get('SUCCESS'):
            dialog = xbmcgui.Dialog()
            dialog.ok('Login Failed', login_data.get('MESSAGE'))
            return None
        sso_id = login_data['USER']['Id']
            
    except:
        xbmc.log(traceback.format_exc())
    return sso_id
    
def get_new_package_ids(sso_id):
    package_ids = []
    try:
        url = build_url('/Interface/GetUserType', params = {'device': 'android', 'ssoid': sso_id, 'sstostage': 'PRD'})
        user_type = get_json_response(url)
        packages = user_type.get('DATA', {}).get('Packages')
        package_ids = [p['PackageId'] for p in packages]
    except:
        xbmc.log(traceback.format_exc())
    return package_ids
    
def get_package_ids():
    package_ids = user_data.get('package_ids') if user_data else []
    if pacakge_ids:
        return package_ids
    package_ids = get_new_package_ids()
    if not package_ids:
        return []
    new_data
    
def get_all_worlds_by_sso_id(last_row, max_count):
    sso_id = user_data['sso_id']
    if not sso_id:
        return
    url = build_url('/home/GetAllWorldsBySSOID', params = {'ssoid': sso_id, 'lastRow':  last_row, 'maxCount':  max_count})
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
    
def get_json_response(url, params = {}):
    response = http_request(url, params = params)
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
user_file = os.path.join(xbmc.translatePath(this_addon.getAddonInfo('profile')), 'user.dat')
user_data = get_user_data(user_file)
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
        '1.0.4': 'Your iWantv addon has been updated.\n\nImprovements included! Enjoy watching!'
        }
    if this_addon.getAddonInfo('version') in messages:
        show_message(messages[this_addon.getAddonInfo('version')], xbmcaddon.Addon().getLocalizedString(50701))
        xbmcaddon.Addon().setSetting('announcement', this_addon.getAddonInfo('version'))

