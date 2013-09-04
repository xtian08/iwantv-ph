import pyamf, httplib
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

    def getBrightCoveData(self, url, contentRefId, userAgent, contentId = 0, amfVersion = pyamf.AMF3, **kwargs):
        #contentOverride = ContentOverride(contentRefId)
        contentOverride = ContentOverride(contentRefId, contentId = contentId)
        viewerExperienceRequest = ViewerExperienceRequest(url, self._experienceId, [contentOverride], self._playerKey)
        client = RemotingService(self._amfUrl, user_agent = userAgent, amf_version = amfVersion)
        for k, v in kwargs.iteritems():
            if k == 'headers':
                for header in v:
                    client.addHTTPHeader(header[0], header[1])
            if k == 'proxy':
                client.setProxy(v)
        service = client.getService('com.brightcove.experience.ExperienceRuntimeFacade')
        return service.getDataForExperience(self._token, viewerExperienceRequest)
        
    def findMediaById(self, playerId, videoPlayer, publisherId, userAgent, amfVersion = pyamf.AMF3, **kwargs):
        client = RemotingService(self._amfUrl, user_agent = userAgent, amf_version = amfVersion)
        service = client.getService('com.brightcove.player.runtime.PlayerMediaFacade')
        for k, v in kwargs.iteritems():
            if k == 'headers':
                for header in v:
                    client.addHTTPHeader(header[0], header[1])
                    pass
            if k == 'proxy':
                client.setProxy(v)
        return service.findMediaById(self._token, playerId, videoPlayer, publisherId)
        
    def findMediaByReferenceId(self, playerId, videoPlayer, publisherId, userAgent, amfVersion = pyamf.AMF3, **kwargs):
        client = RemotingService(self._amfUrl, user_agent = userAgent, amf_version = amfVersion)
        service = client.getService('com.brightcove.player.runtime.PlayerMediaFacade')
        for k, v in kwargs.iteritems():
            if k == 'headers':
                for header in v:
                    client.addHTTPHeader(header[0], header[1])
                    pass
            if k == 'proxy':
                client.setProxy(v)
        return service.findMediaByReferenceId(self._token, playerId, videoPlayer, publisherId)