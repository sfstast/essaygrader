import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select, update
import accounts
from server import app


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.env=patch.dict(os.environ,{'DATABASE_URL':'sqlite:///'+str(Path(self.temp.name)/'accounts.db'),'RENDER':''})
        self.env.start();accounts.attempts.clear();self.client=TestClient(app)

    def tearDown(self):
        accounts.engine().dispose()
        accounts.engine_for.cache_clear();self.env.stop();self.temp.cleanup()

    def signup(self):
        return self.client.post('/api/account/signup',json={
            'username':'Learner_1','password':'A-unique-password-42','display_name':'Maya','learning_goal':'Practice new words.'})

    def test_signup_hashed_password_and_cookie_session(self):
        response=self.signup();self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['user']['username'],'learner_1')
        cookie=response.headers['set-cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=lax',cookie)
        with accounts.engine().connect() as c:
            user=c.execute(select(accounts.users)).mappings().first()
            session=c.execute(select(accounts.sessions)).mappings().first()
        self.assertNotIn('A-unique-password-42',user['password_hash'])
        self.assertTrue(accounts.password_matches('A-unique-password-42',user['password_hash']))
        self.assertNotEqual(session['token_hash'],self.client.cookies.get(accounts.COOKIE))
        self.assertNotIn('password',str(response.json()))
        self.assertEqual(self.client.get('/api/account/me').json()['user']['display_name'],'Maya')

    def test_logout_and_expiry_revoke_access(self):
        self.signup();old=self.client.cookies.get(accounts.COOKIE)
        self.assertEqual(self.client.post('/api/account/logout').status_code,200)
        self.client.cookies.set(accounts.COOKIE,old)
        self.assertIsNone(self.client.get('/api/account/me').json()['user'])
        self.client.cookies.clear();self.signup_login()
        with accounts.engine().begin() as c:c.execute(update(accounts.sessions).values(expires_at=1))
        self.assertIsNone(self.client.get('/api/account/me').json()['user'])

    def signup_login(self):
        return self.client.post('/api/account/login',json={'username':'learner_1','password':'A-unique-password-42'})

    def test_profile_persists_and_other_users_cannot_read_it(self):
        self.signup()
        response=self.client.patch('/api/account/profile',json={'learning_goal':'Use participial phrases.','grade':'Grade 8'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get('/api/account/me').json()['user']['grade'],'Grade 8')
        self.assertEqual(TestClient(app).get('/api/account/history').status_code,401)
        self.assertEqual(self.signup().status_code,409)

    def test_wrong_password_and_cross_origin_account_changes_are_rejected(self):
        self.signup()
        bad=self.client.post('/api/account/login',json={'username':'learner_1','password':'Wrong-password-123'})
        self.assertEqual(bad.status_code,401)
        bad=self.client.post('/api/account/logout',headers={'Origin':'https://other-site.example'})
        self.assertEqual(bad.status_code,403)

    def test_completed_practice_saves_only_a_summary(self):
        from tests.test_vocabulary import vocab_fixture, answers
        import json
        self.signup()
        with patch('server.request_text', return_value=json.dumps(vocab_fixture())):
            response=self.client.post('/api/vocabulary/grade',headers={'X-Model-Key':'private-test-key'},
                                      json={'answers':[answer.model_dump() for answer in answers()]})
        self.assertEqual(response.status_code,200)
        history=self.client.get('/api/account/history').json()['activities']
        self.assertEqual(len(history),1)
        self.assertIn('7/8 points',history[0]['summary'])
        self.assertNotIn('private-test-key',str(history))
        self.assertNotIn('resilient child',str(history))

    def test_database_failures_do_not_expose_connection_details(self):
        from sqlalchemy.exc import SQLAlchemyError
        with patch('accounts.engine', side_effect=SQLAlchemyError('private-database-password')):
            response=self.client.post('/api/account/login',json={
                'username':'learner_1','password':'A-unique-password-42'})
        self.assertEqual(response.status_code,503)
        self.assertNotIn('private-database-password',response.text)

    def test_no_database_does_not_create_ephemeral_production_accounts(self):
        with patch.dict(os.environ,{'DATABASE_URL':'','RENDER':'true'}):
            self.assertFalse(self.client.get('/api/account/me').json()['available'])
            self.assertEqual(self.signup().status_code,503)
        with patch.dict(os.environ,{'DATABASE_URL':'sqlite:///ephemeral.db','RENDER':'true'}):
            self.assertFalse(accounts.available())
