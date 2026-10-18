"""Optional PostgreSQL accounts. No production fallback to ephemeral local files."""
import hashlib
import re
import secrets
import time
from collections import defaultdict, deque
from functools import lru_cache
import os
import threading
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, create_engine, delete, insert, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.pool import StaticPool

router = APIRouter(prefix='/api/account')
metadata = MetaData()
users = Table('studio_users', metadata,
    Column('id', String(40), primary_key=True), Column('username', String(30), unique=True, nullable=False),
    Column('display_name', String(60), nullable=False), Column('password_hash', String(220), nullable=False),
    Column('learning_goal', String(300), nullable=False, default=''),
    Column('grade', String(50), nullable=False, default='Grade 11'), Column('created_at', Integer, nullable=False))
sessions = Table('studio_sessions', metadata,
    Column('token_hash', String(64), primary_key=True),
    Column('user_id', String(40), ForeignKey('studio_users.id'), nullable=False),
    Column('expires_at', Integer, nullable=False))
activities = Table('studio_activities', metadata,
    Column('id', String(40), primary_key=True), Column('user_id', String(40), ForeignKey('studio_users.id'), nullable=False),
    Column('kind', String(30), nullable=False), Column('summary', String(300), nullable=False),
    Column('created_at', Integer, nullable=False))
COOKIE = 'reasoning_session'
SESSION_AGE = 14 * 24 * 60 * 60
attempts = defaultdict(deque)
rate_lock = threading.Lock()


def database_url():
    url = os.getenv('DATABASE_URL', '').strip()
    if url.startswith('postgres://'):
        url = 'postgresql+psycopg://' + url[len('postgres://'):]
    elif url.startswith('postgresql://'):
        url = 'postgresql+psycopg://' + url[len('postgresql://'):]
    # SQLite is permitted only for explicit local development/testing.
    if url.startswith('sqlite') and os.getenv('RENDER'):
        return ''
    return url


def available():
    return bool(database_url())


@lru_cache(maxsize=2)
def engine_for(url):
    if not url:
        raise HTTPException(503, 'Accounts are waiting for a persistent database connection. You can practice as a guest.')
    options = {'pool_pre_ping': True}
    if url.startswith('sqlite'):
        options['connect_args'] = {'check_same_thread': False}
        if ':memory:' in url:
            options['poolclass'] = StaticPool
    else:
        options['connect_args'] = {'connect_timeout': 8, 'prepare_threshold': None}
        options.update(pool_size=3, max_overflow=2, pool_recycle=300)
    engine = create_engine(url, **options)
    metadata.create_all(engine)
    return engine


def engine():
    try:
        return engine_for(database_url())
    except SQLAlchemyError:
        raise HTTPException(503, 'Account storage is unavailable. Please try again later; guest practice still works.') from None


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f'scrypt${salt}${digest}'


def password_matches(password, stored):
    try:
        _, salt, _ = stored.split('$')
        return secrets.compare_digest(password_hash(password, salt), stored)
    except (ValueError, TypeError):
        return False


def csrf(request):
    origin = request.headers.get('origin')
    if origin:
        parsed = urlsplit(origin)
        if parsed.netloc != request.headers.get('host') or parsed.scheme not in ('http','https'):
            raise HTTPException(403, 'Use this site to make account changes.')


def throttle(request, action):
    now = time.time()
    key = (action, request.client.host if request.client else 'unknown')
    with rate_lock:
        if len(attempts) > 5000:
            for item in list(attempts):
                if not attempts[item] or attempts[item][-1] < now-600:
                    attempts.pop(item, None)
        queue = attempts[key]
        while queue and queue[0] < now-300:
            queue.popleft()
        if len(queue) >= 10:
            raise HTTPException(429, 'Too many account attempts. Wait a few minutes before trying again.')
        queue.append(now)


def public_user(row):
    return {key: row[key] for key in ('username','display_name','learning_goal','grade')}


def current_user(request):
    token = request.cookies.get(COOKIE)
    if not available() or not token or len(token) > 200:
        return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    with engine().connect() as connection:
        return connection.execute(select(users).join(sessions, users.c.id == sessions.c.user_id).where(
            sessions.c.token_hash == digest, sessions.c.expires_at > int(time.time()))).mappings().first()


def set_session(request, response, user_id):
    token = secrets.token_urlsafe(40)
    with engine().begin() as connection:
        connection.execute(delete(sessions).where(sessions.c.expires_at <= int(time.time())))
        connection.execute(insert(sessions).values(token_hash=hashlib.sha256(token.encode()).hexdigest(),
                           user_id=user_id, expires_at=int(time.time())+SESSION_AGE))
    response.set_cookie(COOKIE, token, max_age=SESSION_AGE, httponly=True,
                        secure=bool(os.getenv('RENDER')) or request.url.scheme == 'https', samesite='lax', path='/')


class Credentials(BaseModel):
    username: str = Field(min_length=3,max_length=30)
    password: str = Field(min_length=10,max_length=128)

    @field_validator('username')
    @classmethod
    def valid_username(cls,value):
        if not re.fullmatch(r'[A-Za-z0-9_]{3,30}',value):
            raise ValueError('Use 3–30 letters, numbers or underscores for your username.')
        return value.lower()


class SignUp(Credentials):
    display_name: str = Field(default='',max_length=60)
    learning_goal: str = Field(default='',max_length=300)
    grade: str = Field(default='Grade 11',max_length=50)

    @field_validator('grade')
    @classmethod
    def valid_grade(cls,value):
        from grading import GRADE_LEVELS
        if value not in GRADE_LEVELS:
            raise ValueError('Choose a supported grade.')
        return value


class Profile(BaseModel):
    learning_goal: str = Field(max_length=300)
    grade: str = Field(max_length=50)

    @field_validator('grade')
    @classmethod
    def valid_grade(cls,value):
        from grading import GRADE_LEVELS
        if value not in GRADE_LEVELS:
            raise ValueError('Choose a supported grade.')
        return value


@router.get('/me')
def me(request: Request):
    try:
        user = current_user(request)
        return {'available':available(), 'user':public_user(user) if user else None}
    except (HTTPException, SQLAlchemyError):
        return {'available':False, 'user':None}


@router.post('/signup')
def signup(data: SignUp, request: Request, response: Response):
    csrf(request); throttle(request,'signup')
    user_id = secrets.token_hex(16)
    row = dict(id=user_id, username=data.username, display_name=data.display_name.strip() or data.username,
               password_hash=password_hash(data.password), learning_goal=data.learning_goal.strip(),
               grade=data.grade, created_at=int(time.time()))
    try:
        with engine().begin() as connection:
            connection.execute(insert(users).values(**row))
    except IntegrityError:
        raise HTTPException(409,'That username is already taken. Choose another or sign in.') from None
    except SQLAlchemyError:
        raise HTTPException(503,'Could not create your account. Please try again later.') from None
    set_session(request,response,user_id)
    return {'user':public_user(row)}


@router.post('/login')
def login(data: Credentials, request: Request, response: Response):
    csrf(request); throttle(request,'login')
    with engine().connect() as connection:
        user = connection.execute(select(users).where(users.c.username==data.username)).mappings().first()
    if not user or not password_matches(data.password,user['password_hash']):
        if not user:
            password_hash(data.password, '00'*16)
        raise HTTPException(401,'The username or password was not accepted.')
    # Rotate an existing browser session on login.
    previous = request.cookies.get(COOKIE)
    if previous:
        with engine().begin() as connection:
            connection.execute(delete(sessions).where(sessions.c.token_hash==hashlib.sha256(previous.encode()).hexdigest()))
    set_session(request,response,user['id'])
    return {'user':public_user(user)}


@router.post('/logout')
def logout(request: Request,response: Response):
    csrf(request)
    token = request.cookies.get(COOKIE)
    if token and available():
        with engine().begin() as connection:
            connection.execute(delete(sessions).where(sessions.c.token_hash==hashlib.sha256(token.encode()).hexdigest()))
    response.delete_cookie(COOKIE,path='/')
    return {'signed_out':True}


@router.patch('/profile')
def profile(data:Profile,request:Request):
    csrf(request)
    user = current_user(request)
    if not user:
        raise HTTPException(401,'Sign in to save your goal.')
    with engine().begin() as connection:
        connection.execute(update(users).where(users.c.id==user['id']).values(
            learning_goal=data.learning_goal.strip(),grade=data.grade))
    return {'saved':True}


@router.get('/history')
def history(request:Request):
    user=current_user(request)
    if not user:
        raise HTTPException(401,'Sign in to see your progress.')
    with engine().connect() as connection:
        rows=connection.execute(select(activities.c.kind,activities.c.summary,activities.c.created_at).where(
            activities.c.user_id==user['id']).order_by(activities.c.created_at.desc()).limit(20)).mappings().all()
    return {'activities':[dict(row) for row in rows]}


def record_activity(request,kind,summary):
    # Save only a short result summary, never an API key, source passage or draft.
    try:
        user=current_user(request)
        if not user:
            return
        with engine().begin() as connection:
            connection.execute(insert(activities).values(id=secrets.token_hex(16),user_id=user['id'],
                kind=kind,summary=summary[:300],created_at=int(time.time())))
    except (HTTPException, SQLAlchemyError):
        pass  # Optional progress storage must not discard a completed paid review.
