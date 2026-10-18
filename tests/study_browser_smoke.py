"""Browser acceptance checks for goals, vocabulary, sentence practice and accounts."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from tests.test_vocabulary import vocab_fixture
from tests.test_sentence_lab import sentence_fixture
with TemporaryDirectory() as temp:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env=dict(os.environ,DATABASE_URL='sqlite:///'+str(Path(temp)/'accounts.db'),RENDER='')
    server=subprocess.Popen([sys.executable,'-m','uvicorn','server:app','--host','127.0.0.1','--port',str(port)],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    base=f'http://127.0.0.1:{port}'
    try:
        for _ in range(100):
            try:
                if urlopen(base+'/api/health',timeout=1).status==200:break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Test server failed to start')
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,executable_path=shutil.which('chromium'))
            page=browser.new_page(viewport={'width':1440,'height':1080})
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(base);page.locator('#start-learning').wait_for(state='visible')
            page.wait_for_function("!document.getElementById('start-learning').disabled")
            assert page.locator('#welcome').is_visible()
            page.locator('#learning-goal').fill('Use my study words naturally.')
            page.locator('#welcome-grade').select_option('Grade 8')
            page.locator('#account-open').click()
            page.wait_for_function("!document.getElementById('account-submit').disabled")
            page.locator('#account-name').fill('Study tester')
            page.locator('#account-username').fill('study_tester')
            page.locator('#account-password').fill('Browser-only-test-123')
            page.locator('#account-submit').click()
            page.locator('#account-member').wait_for(state='visible')
            assert page.locator('#account-password').input_value()==''
            assert 'reasoning_session' not in page.evaluate('document.cookie')
            page.locator('#account-close').click()
            page.locator('input[name="focus"][value="vocabulary"]').check()
            assert page.locator('#welcome-grade').input_value()=='Grade 8'
            page.locator('#start-learning').click();page.locator('#vocabulary-tools').wait_for(state='visible')
            assert page.locator('#grade').input_value()=='Grade 8'
            page.locator('#vocab-words').fill('resilient: able to recover\nmeticulous')
            page.locator('#build-vocab').click()
            assert page.locator('.vocab-answer-card').count()==2
            page.locator('#vocab-definition-0').fill('Able to recover after a setback.')
            page.locator('#vocab-sentence-0').fill('The resilient child kept trying after the first attempt failed.')
            page.locator('#vocab-definition-1').fill('Very careful with details.')
            page.locator('#vocab-sentence-1').fill('The meticulous chef weighed every ingredient.')
            page.locator('#grade-vocab').click()
            assert 'Anthropic key' in page.locator('#vocab-message').inner_text()
            page.locator('#api-key').fill('fake-key')
            vocab_calls=[]
            def vocabulary(route):
                data=route.request.post_data_json;vocab_calls.append(data)
                assert len(data['answers'])==2 and data['grade']=='Grade 8'
                assert 'paragraph' not in data and 'source' not in data
                result=vocab_fixture();rows=[{**row,'points':row['meaning_score']+row['usage_score']} for row in result['results']]
                rows[0]['example_sentence']='<script>window.vocabUnsafe=true</script>'
                route.fulfill(json={'results':rows,'earned':7,'possible':8,'percentage':88,'review_words':['resilient'],'grading_note':'Practice feedback.'})
            page.route('**/api/vocabulary/grade',vocabulary)
            page.locator('#grade-vocab').click();page.locator('#vocab-results').wait_for(state='visible')
            assert '7 / 8 points' in page.locator('#vocab-score').inner_text()
            assert page.evaluate('window.vocabUnsafe') is None
            page.locator('#grade-vocab').click()
            assert 'existing review' in page.locator('#vocab-message').inner_text();assert len(vocab_calls)==1
            page.locator('#vocab-definition-0').fill('Able to bounce back.')
            assert page.locator('#vocab-stale').is_visible()
            page.locator('#writing-tab').click();page.locator('#vocabulary-tab').click()
            assert page.locator('#vocab-definition-0').input_value()=='Able to bounce back.'
            page.screenshot(path='/tmp/reasoning-studio-vocabulary.png',full_page=True)
            page.locator('#sentences-tab').click()
            page.wait_for_function("!document.getElementById('check-identify').disabled")
            bank=json.load(urlopen(base+'/api/sentence-lab'))['exercises']
            sentence=page.locator('#identify-sentence').inner_text()
            expected=next(row['target_id'] for row in bank if row['sentence']==sentence)
            page.locator(f'input[name="identify-answer"][value="{expected}"]').check()
            page.locator('#check-identify').click()
            assert '1 correct' in page.locator('#identify-progress').inner_text()
            assert page.locator('#check-identify').is_disabled()
            page.locator('#identify-category').select_option('structures')
            assert page.locator('input[name="identify-answer"]').count()==4
            page.locator('#write-mode').click();page.locator('#sentence-target').select_option('participial')
            page.locator('#practice-sentence').fill('Exhausted by the climb, Mara rested.')
            sentence_calls=[]
            def writing(route):
                data=route.request.post_data_json;sentence_calls.append(data)
                assert data['target_id']=='participial'
                assert 'paragraph' not in data and 'answers' not in data
                route.fulfill(json={**sentence_fixture(),'target_label':'Participial phrase','note':'Practice feedback.'})
            page.route('**/api/sentence-lab/review',writing)
            page.locator('#review-sentence').click();page.locator('#sentence-result').wait_for(state='visible')
            assert 'Target demonstrated' in page.locator('#sentence-verdict').inner_text()
            page.locator('#review-sentence').click();assert len(sentence_calls)==1
            page.locator('#practice-sentence').fill('Carrying a map, Mara followed the path.')
            assert page.locator('#sentence-result-stale').is_visible()
            page.locator('#account-open').click();page.locator('#account-member').wait_for(state='visible')
            page.locator('#save-profile').click()
            assert 'saved' in page.locator('#account-message').inner_text()
            page.locator('#account-logout').click();page.locator('#account-guest').wait_for(state='visible')
            page.locator('#account-close').click()
            assert page.locator('#api-key').input_value()==''
            page.locator('a[aria-label="Reasoning Studio home"]').click()
            page.screenshot(path='/tmp/reasoning-studio-welcome.png',full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path='/tmp/reasoning-studio-welcome-mobile.png',full_page=True)
            page.locator('input[name="focus"][value="sentences"]').check();page.locator('#start-learning').click()
            page.locator('#sentence-tools').wait_for(state='visible')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path='/tmp/reasoning-studio-sentence-mobile.png',full_page=True)
            assert page.evaluate('localStorage.length')==0 and page.evaluate('sessionStorage.length')==0
            assert not errors,errors
            browser.close()
        print('PASS study browser: welcome goals, account signup/logout/profile, vocabulary grading/reuse, free identification, sentence review/reuse, safe rendering, state preservation, mobile layout')
    finally:
        server.terminate();server.wait(timeout=10)
