"""Google, Apple and Microsoft OpenID Connect with verified, distinct identities."""
import json
import logging
import os
import re
import secrets
import time
from urllib.parse import urlsplit

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from joserfc import jwt
from joserfc.jwk import ECKey
from sqlalchemy import Column, ForeignKey, Integer, String, Table, insert, select
from sqlalchemy.exc import IntegrityError

import accounts

router = APIRouter(prefix='/api/account/oauth')
identities = Table('studio_social_identities', accounts.metadata,
    Column('provider',String(20),primary_key=True), Column('issuer',String(255),primary_key=True),
    Column('subject',String(255),primary_key=True),
    Column('user_id',String(40),ForeignKey('studio_users.id'),nullable=False),
    Column('created_at',Integer,nullable=False))
PROVIDERS = {
    'google': {'label':'Google', 'variables':('GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET'),
               'metadata':'https://accounts.google.com/.well-known/openid-configuration'},
    'apple': {'label':'Apple', 'variables':('APPLE_CLIENT_ID','APPLE_TEAM_ID','APPLE_KEY_ID','APPLE_PRIVATE_KEY'),
              'metadata':'https://appleid.apple.com/.well-known/openid-configuration'},
    'microsoft': {'label':'Microsoft', 'variables':('MICROSOFT_CLIENT_ID','MICROSOFT_CLIENT_SECRET')},
}


class OAuthAccessLogFilter(logging.Filter):
    """Do not write authorization codes or state query parameters to access logs."""
    def filter(self, record):
        if isinstance(record.args,tuple) and len(record.args)>=3:
            path=record.args[2]
            if isinstance(path,str) and path.startswith('/api/account/oauth/'):
                args=list(record.args);args[2]=path.split('?',1)[0];record.args=tuple(args)
        return True


logging.getLogger('uvicorn.access').addFilter(OAuthAccessLogFilter())


def public_base_url():
    url=os.getenv('PUBLIC_BASE_URL',os.getenv('RENDER_EXTERNAL_URL','https://reasoning-studio.onrender.com')).rstrip('/')
    parts=urlsplit(url)
    if (not parts.netloc or parts.path or parts.query or parts.fragment or parts.username
            or parts.scheme not in ('http','https') or (os.getenv('RENDER') and parts.scheme!='https')):
        raise HTTPException(503,'Sign-in is not configured correctly yet. Guest practice still works.')
    return url


def provider_status():
    session_ready=len(os.getenv('OAUTH_SESSION_SECRET',''))>=32
    return [{'id':name,'label':config['label'],
             'configured':session_ready and all(os.getenv(key,'').strip() for key in config['variables']),
             'ready':accounts.available() and session_ready and all(os.getenv(key,'').strip() for key in config['variables'])}
            for name,config in PROVIDERS.items()]


def require_provider(provider):
    status=next((item for item in provider_status() if item['id']==provider),None)
    if status is None:
        raise HTTPException(404,'Choose a supported sign-in provider.')
    if not status['ready']:
        raise HTTPException(503,f"{status['label']} sign-in is not enabled yet. You can practice as a guest.")


def apple_client_secret():
    now=int(time.time())
    key=ECKey.import_key(os.environ['APPLE_PRIVATE_KEY'].replace('\\n','\n'))
    return jwt.encode({'alg':'ES256','kid':os.environ['APPLE_KEY_ID']},
                      {'iss':os.environ['APPLE_TEAM_ID'],'sub':os.environ['APPLE_CLIENT_ID'],
                       'aud':'https://appleid.apple.com','iat':now,'exp':now+300},key)


def microsoft_tenant():
    tenant=os.getenv('MICROSOFT_TENANT_ID','common').lower()
    if tenant not in ('common','organizations','consumers') and not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',tenant):
        raise HTTPException(503,'Microsoft sign-in is not configured correctly yet.')
    return tenant


def microsoft_issuer(claims,issuer):
    tenant=claims.get('tid','')
    if not isinstance(tenant,str) or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',tenant):
        return False
    configured=microsoft_tenant()
    consumer='9188040d-6c67-4c5b-b112-36a304b66dad'
    if configured=='consumers' and tenant!=consumer:
        return False
    if configured=='organizations' and tenant==consumer:
        return False
    if configured not in ('common','consumers','organizations') and tenant!=configured:
        return False
    return issuer==f'https://login.microsoftonline.com/{tenant}/v2.0'


def oauth_client(provider):
    config=PROVIDERS[provider]
    if provider=='apple':
        secret=apple_client_secret()
        client_kwargs={'scope':'openid name','token_endpoint_auth_method':'client_secret_post'}
        metadata=config['metadata']
    else:
        secret=os.environ[provider.upper()+'_CLIENT_SECRET']
        client_kwargs={'scope':'openid profile','code_challenge_method':'S256',
                       'token_endpoint_auth_method':'client_secret_post'}
        metadata=(f'https://login.microsoftonline.com/{microsoft_tenant()}/v2.0/.well-known/openid-configuration'
                  if provider=='microsoft' else config['metadata'])
    return OAuth().register(provider,client_id=os.environ[provider.upper()+'_CLIENT_ID'],
                            client_secret=secret,server_metadata_url=metadata,client_kwargs=client_kwargs)


def resolve_identity(provider,claims,display_name=''):
    issuer,subject=claims.get('iss'),claims.get('sub')
    if not isinstance(subject,str) or not subject or len(subject)>255 or not isinstance(issuer,str) or len(issuer)>255:
        raise ValueError('Invalid identity claims')
    where=(identities.c.provider==provider,identities.c.issuer==issuer,identities.c.subject==subject)

    def lookup(connection):
        return connection.execute(select(accounts.users).join(identities,accounts.users.c.id==identities.c.user_id).where(*where)).mappings().first()

    try:
        with accounts.engine().begin() as connection:
            existing=lookup(connection)
            if existing:
                return dict(existing)
            name=display_name or claims.get('name')
            if not isinstance(name,str) or not name.strip():
                name=PROVIDERS[provider]['label']+' learner'
            user=dict(id=secrets.token_hex(16),username=provider+'_'+secrets.token_hex(8),
                      display_name=name.strip()[:60],password_hash='!social-sign-in-only!',
                      learning_goal='',grade='Grade 11',created_at=int(time.time()))
            connection.execute(insert(accounts.users).values(**user))
            connection.execute(insert(identities).values(provider=provider,issuer=issuer,subject=subject,
                                                        user_id=user['id'],created_at=int(time.time())))
            return user
    except IntegrityError:
        # Two callbacks for the same new identity must not create duplicate accounts.
        with accounts.engine().connect() as connection:
            existing=lookup(connection)
            if existing:
                return dict(existing)
        raise


def completion_response(status):
    origin=public_base_url()
    message=json.dumps({'type':'studio-auth','status':status})
    target=json.dumps(origin)
    # Only a status is sent to the opener: no identity tokens, access tokens or user data.
    content=('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
             'content="width=device-width,initial-scale=1"><title>Sign-in — Reasoning Studio</title></head>'
             '<body><p>You can close this window and return to Reasoning Studio.</p><script>'
             f'if(window.opener){{window.opener.postMessage({message},{target});window.close();}}'
             f'else{{window.location.replace({target}+"/#welcome");}}'
             '</script></body></html>')
    response=HTMLResponse(content,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer',
                                           'X-Content-Type-Options':'nosniff'})
    return response


@router.get('/{provider}/start')
async def start(provider:str,request:Request):
    require_provider(provider);accounts.throttle(request,'oauth-'+provider)
    # Check storage before sending someone through a provider consent screen.
    accounts.engine()
    request.session.clear()
    redirect=public_base_url()+f'/api/account/oauth/{provider}/callback'
    try:
        client=oauth_client(provider)
        params={'response_mode':'form_post'} if provider=='apple' else {'prompt':'select_account'}
        return await client.authorize_redirect(request,redirect,**params)
    except HTTPException:
        raise
    except Exception:
        request.session.clear()
        raise HTTPException(503,'Could not start sign-in. Please try again later; guest practice still works.') from None


@router.api_route('/{provider}/callback',methods=['GET','POST'])
async def callback(provider:str,request:Request):
    require_provider(provider)
    try:
        client=oauth_client(provider)
        kwargs={'claims_options':{'iss':{'essential':True,'validate':microsoft_issuer}}} if provider=='microsoft' else {}
        token=await client.authorize_access_token(request,**kwargs)
        # Authlib validates state, signature, issuer, audience, expiry and the stored nonce.
        claims=token.get('userinfo')
        if not claims:
            raise ValueError('No verified identity')
        name=''
        if provider=='apple' and request.method=='POST':
            form=await request.form()
            hint=form.get('user','')
            if isinstance(hint,str) and len(hint)<=2048:
                try:
                    info=json.loads(hint);parts=info.get('name',{})
                    name=' '.join(v for k in ('firstName','lastName') if isinstance((v:=parts.get(k)),str))[:60]
                except (ValueError,AttributeError,TypeError):
                    pass  # First-login name is a display hint, never proof of identity.
        user=resolve_identity(provider,claims,name)
        response=completion_response('success')
        accounts.set_session(request,response,user['id'])
    except Exception:
        # Never expose provider error descriptions, authorization codes or tokens.
        response=completion_response('error')
    request.session.clear()
    return response
