"""Exercise real Authlib state/nonce/JWT checks against mocked provider endpoints."""
import json
import base64
import hashlib
import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from fastapi.testclient import TestClient
import httpx2
from joserfc import jwt
from joserfc.jwk import RSAKey, ECKey
from sqlalchemy import func, select

import accounts
import social_auth
from server import app


class SocialAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rsa=RSAKey.generate_key(2048,parameters={'kid':'provider-test-key'})
        cls.apple_key=ECKey.generate_key('P-256',parameters={'kid':'apple-test-key'})

    def setUp(self):
        self.temp=TemporaryDirectory()
        self.env=patch.dict(os.environ,{
            'DATABASE_URL':'sqlite:///'+str(Path(self.temp.name)/'accounts.db'),'RENDER':'',
            'PUBLIC_BASE_URL':'http://testserver','OAUTH_SESSION_SECRET':'test-state-secret-'*4,
            'GOOGLE_CLIENT_ID':'google-test-client','GOOGLE_CLIENT_SECRET':'private-google-secret',
            'MICROSOFT_CLIENT_ID':'microsoft-test-client','MICROSOFT_CLIENT_SECRET':'private-ms-secret',
            'MICROSOFT_TENANT_ID':'common','APPLE_CLIENT_ID':'studio.apple.web',
            'APPLE_TEAM_ID':'APPLE_TEAM','APPLE_KEY_ID':'apple-test-key',
            'APPLE_PRIVATE_KEY':self.apple_key.as_pem(private=True).decode(),
        })
        self.env.start();accounts.attempts.clear();self.client=TestClient(app)
        self.nonce='';self.claim_changes={};self.token_calls=0;self.subject='subject-1'
        self.provider='google';self.tenant='11111111-2222-3333-4444-555555555555'
        original=social_auth.oauth_client
        def client_for(provider):
            client=original(provider);client.client_kwargs['transport']=httpx2.MockTransport(self.respond)
            return client
        self.patch_client=patch('social_auth.oauth_client',side_effect=client_for);self.patch_client.start()

    def tearDown(self):
        accounts.engine().dispose();accounts.engine_for.cache_clear();self.patch_client.stop()
        self.env.stop();self.temp.cleanup()

    def issuer(self):
        return {'google':'https://accounts.google.com','apple':'https://appleid.apple.com',
                'microsoft':f'https://login.microsoftonline.com/{self.tenant}/v2.0'}[self.provider]

    def respond(self,request):
        url=str(request.url)
        if '.well-known/openid-configuration' in url:
            issuer='https://login.microsoftonline.com/{tenantid}/v2.0' if self.provider=='microsoft' else self.issuer()
            return httpx2.Response(200,json={'issuer':issuer,
                'authorization_endpoint':'https://provider.example/authorize','token_endpoint':'https://provider.example/token',
                'jwks_uri':'https://provider.example/keys','response_types_supported':['code'],
                'id_token_signing_alg_values_supported':['RS256']})
        if url=='https://provider.example/keys':
            return httpx2.Response(200,json={'keys':[self.rsa.as_dict(private=False)]})
        if url=='https://provider.example/token':
            self.token_calls+=1
            body=parse_qs(request.content.decode())
            if self.provider!='apple':
                verifier=body['code_verifier'][0]
                challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
                self.assertEqual(challenge,self.challenge)
            claims={'iss':self.issuer(),'sub':self.subject,'aud':os.environ[self.provider.upper()+'_CLIENT_ID'],
                    'iat':int(time.time()),'exp':int(time.time())+300,'nonce':self.nonce,
                    'name':'Social learner','email':'same-address@example.org'}
            if self.provider=='microsoft':claims['tid']=self.tenant
            claims.update(self.claim_changes)
            token=jwt.encode({'alg':'RS256','kid':'provider-test-key'},claims,getattr(self,'signing_key',self.rsa))
            return httpx2.Response(200,json={'access_token':'provider-only-access-token','token_type':'Bearer','id_token':token})
        raise AssertionError('Unexpected provider URL '+url)

    def begin(self,provider='google'):
        self.provider=provider
        response=self.client.get(f'/api/account/oauth/{provider}/start',follow_redirects=False)
        self.assertEqual(response.status_code,302,response.text)
        params=parse_qs(urlsplit(response.headers['location']).query)
        self.nonce=params['nonce'][0]
        self.challenge=params.get('code_challenge',[''])[0]
        if provider!='apple':self.assertEqual(params['code_challenge_method'],['S256'])
        return params['state'][0]

    def complete(self,state,provider='google'):
        path=f'/api/account/oauth/{provider}/callback'
        if provider=='apple':
            return self.client.post(path,data={'code':'provider-code','state':state,
                'user':json.dumps({'name':{'firstName':'Ada','lastName':'Lovelace'},'email':'untrusted@example.net'})})
        return self.client.get(path,params={'code':'provider-code','state':state})

    def count_users(self):
        with accounts.engine().connect() as connection:
            return connection.scalar(select(func.count()).select_from(accounts.users))

    def test_verified_google_signup_and_repeat_login_reuse_account(self):
        state=self.begin();response=self.complete(state)
        self.assertIn('"status": "success"',response.text)
        self.assertNotIn('provider-only-access-token',response.text)
        self.assertNotIn('provider-code',response.text)
        first=self.client.get('/api/account/me').json()['user']
        self.assertIsNotNone(first)
        self.assertEqual(self.count_users(),1)
        response=self.complete(self.begin())
        self.assertIn('"status": "success"',response.text)
        self.assertEqual(self.client.get('/api/account/me').json()['user']['username'],first['username'])
        self.assertEqual(self.count_users(),1)
        with accounts.engine().connect() as connection:
            self.assertEqual(connection.scalar(select(func.count()).select_from(accounts.sessions)),1)

    def test_mismatched_and_replayed_state_do_not_create_session(self):
        self.begin();response=self.complete('forged-state')
        self.assertIn('"status": "error"',response.text);self.assertEqual(self.token_calls,0)
        self.assertIsNone(self.client.get('/api/account/me').json()['user'])
        state=self.begin();self.complete(state)
        calls=self.token_calls
        response=self.complete(state)
        self.assertIn('"status": "error"',response.text);self.assertEqual(self.token_calls,calls)

    def test_wrong_nonce_audience_issuer_and_expiry_are_rejected(self):
        for change in [{'nonce':'wrong-nonce'},{'aud':'other-application'},
                       {'iss':'https://attacker.example'},{'exp':int(time.time())-600}]:
            self.claim_changes=change
            response=self.complete(self.begin())
            self.assertIn('"status": "error"',response.text)
            self.assertIsNone(self.client.get('/api/account/me').json()['user'])
        self.assertEqual(self.count_users(),0)

    def test_token_with_wrong_signature_does_not_sign_in(self):
        self.signing_key=RSAKey.generate_key(2048,parameters={'kid':'provider-test-key'})
        response=self.complete(self.begin())
        self.assertIn('"status": "error"',response.text)
        self.assertIsNone(self.client.get('/api/account/me').json()['user'])
        self.assertEqual(self.count_users(),0)

    def test_apple_form_post_uses_verified_identity_not_posted_email(self):
        state=self.begin('apple');response=self.complete(state,'apple')
        self.assertIn('"status": "success"',response.text)
        user=self.client.get('/api/account/me').json()['user']
        self.assertEqual(user['display_name'],'Ada Lovelace')
        self.assertNotIn('email',user)
        with accounts.engine().connect() as connection:
            stored=connection.execute(select(accounts.users)).mappings().first()
        self.assertFalse(accounts.password_matches('any-user-password',stored['password_hash']))
        token=social_auth.apple_client_secret()
        claims=jwt.decode(token,self.apple_key).claims
        self.assertEqual(claims['iss'],'APPLE_TEAM');self.assertEqual(claims['sub'],'studio.apple.web')
        self.assertLessEqual(claims['exp']-claims['iat'],300)

    def test_microsoft_common_validates_tenant_issuer_and_scopes_identity(self):
        response=self.complete(self.begin('microsoft'),'microsoft')
        self.assertIn('"status": "success"',response.text)
        self.tenant='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
        response=self.complete(self.begin('microsoft'),'microsoft')
        self.assertIn('"status": "success"',response.text);self.assertEqual(self.count_users(),2)
        self.claim_changes={'iss':'https://attacker.example'}
        response=self.complete(self.begin('microsoft'),'microsoft')
        self.assertIn('"status": "error"',response.text);self.assertEqual(self.count_users(),2)

    def test_same_email_never_implicitly_links_different_provider_identities(self):
        self.complete(self.begin('google'),'google')
        self.complete(self.begin('apple'),'apple')
        self.assertEqual(self.count_users(),2)

    def test_configuration_missing_and_unknown_providers_are_disabled(self):
        self.assertEqual(self.client.get('/api/account/oauth/unknown/start').status_code,404)
        with patch.dict(os.environ,{'GOOGLE_CLIENT_SECRET':''}):
            self.assertEqual(self.client.get('/api/account/oauth/google/start').status_code,503)
            status=self.client.get('/api/account/me').json()['social_providers']
            self.assertFalse(next(p for p in status if p['id']=='google')['ready'])
            self.assertNotIn('private-ms-secret',str(status))

    def test_callback_codes_are_redacted_from_access_logs(self):
        record=logging.LogRecord('uvicorn.access',logging.INFO,'',1,'%s - "%s %s HTTP/%s" %s',
            ('client','GET','/api/account/oauth/google/callback?code=private-code&state=private-state','1.1',200),None)
        social_auth.OAuthAccessLogFilter().filter(record)
        self.assertNotIn('private-code',record.getMessage());self.assertNotIn('private-state',record.getMessage())
        self.assertIn('/api/account/oauth/google/callback',record.getMessage())
