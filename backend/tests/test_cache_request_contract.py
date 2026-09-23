from types import SimpleNamespace
import json
import httpx
from app import project_cache

def test_refresh_requests_supported_fields_and_keeps_server_metadata(monkeypatch):
    monkeypatch.setattr(project_cache,'get_settings',lambda:SimpleNamespace(project_cache_url='https://webdev.test',project_cache_username='user',project_cache_password='secret'))
    def respond(request):
        if request.url.path=='/auth/login':return httpx.Response(200,json={'token':'session'})
        assert request.url.path=='/projects/cache'
        assert json.loads(request.content)=={'fields':{'settings':True,'head':True,'data':True},'names':['own.test']}
        assert request.headers['Authorization']=='Bearer session'
        return httpx.Response(201,json=[{'name':'own.test','serverIp':'shark','settings':{},'head':{}}])
    client=httpx.Client
    monkeypatch.setattr(project_cache.httpx,'Client',lambda **kw:client(transport=httpx.MockTransport(respond),**kw))
    assert project_cache.fetch_project_cache(['own.test'])[0]['serverIp']=='shark'
