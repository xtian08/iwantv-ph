import pyamf
from pyamf.remoting.client import RemotingService
from pyamf import remoting, amf3, util

class ViewerExperienceRequest(object):
    def __init__(self, URL, experienceId, contentOverrides, playerKey, TTLToken='', deliveryType = float(0)):
        self.URL = URL
        self.experienceId = experienceId
        self.contentOverrides = contentOverrides
        self.playerKey = playerKey
        self.TTLToken = TTLToken
        self.deliveryType = deliveryType

class ContentOverride(object):
    def __init__(self, contentRefId, featureId = float(0), contentId = 0, contentType=0, target='videoPlayer'):
        self.featureId = featureId
        self.contentId = contentId
        self.contentType = contentType
        self.featuredRefId = None
        self.contentIds = None
        self.contentRefId = contentRefId
        self.target = target
        self.contentRefIds = None

class BrightCove(object):
    def __init__(self, token, playerKey, experienceId, serviceUrl = 'http://c.brightcove.com/services/messagebroker/amf'):
        self._token = token
        self._playerKey = playerKey
        self._experienceId = experienceId
        self._amfUrl = serviceUrl + '?playerKey=' + playerKey
        pyamf.register_class(ViewerExperienceRequest, 'com.brightcove.experience.ViewerExperienceRequest')
        pyamf.register_class(ContentOverride, 'com.brightcove.experience.ContentOverride')
        
    def _buildAmfRequest(self, body, target):
        env = remoting.Envelope(amfVersion = 3)
        env.bodies.append(
            (
                "/1",
                remoting.Request(
                    target = target,
                    body = body,
                    envelope = env
                )
            )
        )
        return env
        
    def _sendAmfRequest(self, envelope, **kwargs):
        body = remoting.encode(envelope).read()
        headers = {'content-type': 'application/x-amf'}
        proxy = []
        for k, v in kwargs.iteritems():
            if k == 'headers':
                for header in v:
                    headers[header[0]] = header[1]
            if k == 'proxy':
                hasProxy = True
                if v.find(':'):
                    proxyHost, proxyPort = v.split(':')
                else:
                    proxyHost = v
                    proxyPort = '80'
                proxy = [proxyHost, int(proxyPort)]
        response = ''
        try:
            import httplib
            conn = httplib.HTTPConnection('c.brightcove.com')
            if proxy:
                conn = httplib.HTTPConnection(proxyHost, proxyPort)
            conn.request("POST", self._amfUrl, body, headers)
            response = conn.getresponse().read()
        except UnicodeDecodeError:
            import lib.xhttplib as xhttplib
            conn = xhttplib.HTTPConnection('c.brightcove.com')
            if proxy:
                conn = xhttplib.HTTPConnection(proxyHost, proxyPort)
            conn.request("POST", self._amfUrl, body, headers)
            response = conn.getresponse().read()
        response = remoting.decode(response).bodies[0][1].body
        return response

    def getBrightCoveData(self, url, contentRefId, userAgent, contentId = 0, **kwargs):
        contentOverride = ContentOverride(contentRefId, contentId = contentId)
        viewerExperienceRequest = ViewerExperienceRequest(url, self._experienceId, [contentOverride], self._playerKey)
        envelope = self._buildAmfRequest(
        [self._token, viewerExperienceRequest], 'com.brightcove.experience.ExperienceRuntimeFacade.getDataForExperience')
        response = self._sendAmfRequest(envelope, **kwargs)
        return response 

    def findMediaById(self, playerId, videoPlayer, publisherId, userAgent, **kwargs):
        envelope = self._buildAmfRequest(
        [self._token, playerId, videoPlayer, publisherId], 'com.brightcove.player.runtime.PlayerMediaFacade.findMediaById')
        response = self._sendAmfRequest(envelope, **kwargs)
        return response
        
    def findMediaByReferenceId(self, playerId, videoPlayer, publisherId, userAgent, **kwargs):
        envelope = self._buildAmfRequest(
        [self._token, playerId, videoPlayer, publisherId], 'com.brightcove.player.runtime.PlayerMediaFacade.findMediaByReferenceId')
        response = self._sendAmfRequest(envelope, **kwargs)
        return response
 
