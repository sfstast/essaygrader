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
    env=dict(os.environ,DATABASE_URL='sqlite:///'+str(Path(temp)/'accounts.db'),RENDER='',OAUTH_SESSION_SECRET='browser-test-session-secret-'*3,GOOGLE_CLIENT_ID='fake-google-client',GOOGLE_CLIENT_SECRET='fake-google-secret')
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
            if not page.locator('#classroom-settings').evaluate('(el) => el.open'):
                page.locator('#classroom-settings > summary').click()
            page.locator('#api-key').fill('fake-key')
            page.locator('#classroom-settings > summary').click()
            assert not page.locator('#api-key').is_visible()
            assert 'AI key entered' in page.locator('#setup-summary').inner_text()
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
            assert '8.8 / 10' in page.locator('#vocab-score').inner_text()
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
            page.locator('#identify-hint-button').click()
            assert page.locator('#identify-hint').is_visible()
            page.locator('#identify-hint-button').click()
            assert page.locator('#identify-hint-button').is_disabled()
            page.locator(f'input[name="identify-answer"][value="{expected}"]').check()
            page.locator('#check-identify').click()
            assert '1 correct' in page.locator('#identify-progress').inner_text()
            assert '10.0/10' in page.locator('#identify-progress').inner_text()
            assert page.locator('#check-identify').is_disabled()
            page.locator('#identify-category').select_option('structures')
            assert page.locator('input[name="identify-answer"]').count()==4
            page.locator('#write-mode').click();page.locator('#sentence-target').select_option('participial')
            assert page.locator('#identify-hint').is_hidden()
            assert page.locator('#sentence-guide li').count()==3
            assert 'dangling' in page.locator('#sentence-watch').inner_text()
            page.locator('#sentence-starter-guide summary').click()
            assert 'Carrying' in page.locator('#sentence-starter').inner_text()
            original_topic=page.locator('#sentence-topic').input_value()
            seen_prompts={page.locator('#sentence-topic-prompt').inner_text()}
            for _ in range(15):
                page.locator('#new-sentence-prompt').click()
                prompt=page.locator('#sentence-topic-prompt').inner_text()
                assert prompt not in seen_prompts
                seen_prompts.add(prompt)
                assert page.locator('#sentence-topic').input_value()==original_topic
            page.locator('#surprise-topic').click()
            assert page.locator('#sentence-topic').input_value()!=original_topic
            page.locator('#practice-sentence').fill('Exhausted by the climb, Mara rested.')
            page.locator('#sentence-topic').select_option('custom')
            page.locator('#sentence-custom-topic').fill('A hiking adventure <img src=x>')
            assert page.locator('#new-sentence-prompt').is_disabled()
            assert page.locator('#sentence-topic-prompt img').count()==0
            assert page.locator('#practice-sentence').input_value()=='Exhausted by the climb, Mara rested.'
            sentence_calls=[];sentence_failure=[True]
            def writing(route):
                if sentence_failure[0]:
                    sentence_failure[0]=False
                    route.fulfill(status=502,json={'detail':'Claude returned an incomplete review. Your work is kept; please try again.'})
                    return
                data=route.request.post_data_json;sentence_calls.append(data)
                assert data['target_id']=='participial'
                assert data['writing_topic']=='A hiking adventure <img src=x>'
                assert 'paragraph' not in data and 'answers' not in data
                route.fulfill(json={**sentence_fixture(),'target_label':'Participial phrase','note':'Practice feedback.'})
            page.route('**/api/sentence-lab/review',writing)
            page.locator('#review-sentence').click()
            page.wait_for_function("document.getElementById('sentence-message').textContent.includes('incomplete review')")
            assert page.locator('#practice-sentence').input_value()=='Exhausted by the climb, Mara rested.'
            assert page.locator('#sentence-result').is_hidden()
            page.locator('#review-sentence').click();page.locator('#sentence-result').wait_for(state='visible')
            assert 'Target demonstrated' in page.locator('#sentence-verdict').inner_text()
            assert '10 / 10' in page.locator('#sentence-score').inner_text()
            assert 'Clarity 2/2' in page.locator('#sentence-score-breakdown').inner_text()
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
            # Topic selection on the welcome page drives questions and writing targets.
            page.locator('a[aria-label="Reasoning Studio home"]').click()
            page.locator('input[name="focus"][value="sentences"]').check()
            page.locator('#welcome-pattern-picker').wait_for(state='visible')
            page.locator('#welcome-pattern-picker [data-pattern-preset="clear"]').click()
            assert page.locator('#start-learning').is_disabled()
            page.locator('#welcome-pattern-choices input[data-pattern-id="participial"]').check()
            page.locator('#welcome-pattern-choices input[data-pattern-id="appositive"]').check()
            assert '2 patterns' in page.locator('#start-learning').inner_text()
            page.locator('#start-learning').click();page.locator('#sentence-tools').wait_for(state='visible')
            page.locator('#identify-mode').click()
            assert set(page.locator('#sentence-target option').evaluate_all('(nodes)=>nodes.map(node=>node.value)'))=={'participial','appositive'}
            for _ in range(6):
                sentence=page.locator('#identify-sentence').inner_text()
                expected=next(row['target_id'] for row in bank if row['sentence']==sentence)
                assert expected in {'participial','appositive'}
                page.locator('#next-identify').click()
            page.locator('#sentence-tools [data-pattern-preset="clear"]').click()
            assert page.locator('#review-sentence').is_disabled()
            page.locator('#sentence-pattern-choices input[data-pattern-id="gerund"]').check()
            assert page.locator('#sentence-target').input_value()=='gerund'
            assert page.locator('#practice-sentence').input_value()=='Carrying a map, Mara followed the path.'
            # A simulated provider popup exercises real account cookies and preserves the tab.
            page.locator('#writing-tab').click()
            page.locator('#writing-tools').wait_for(state='visible')
            page.locator('#source').fill('Keep my source text.')
            page.locator('#paragraph').fill('Keep my working draft.')
            if not page.locator('#classroom-settings').evaluate('(el) => el.open'):
                page.locator('#classroom-settings > summary').click()
            page.locator('#api-key').fill('do-not-save-test-key')
            page.locator('#account-open').click()
            page.wait_for_function("!document.querySelector('[data-social-provider=google]').disabled")
            assert page.locator('[data-social-provider="apple"]').is_disabled()
            popup_html = """<!doctype html><script>(async()=>{
              const response=await fetch('/api/account/signup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'social_browser',password:'Only-a-browser-fixture-123',display_name:'Social browser'})});
              window.opener.postMessage({type:'studio-auth',status:response.ok?'success':'error'},location.origin);window.close();
            })();</script>"""
            page.context.route('**/api/account/oauth/google/start',lambda route:route.fulfill(content_type='text/html',body=popup_html))
            with page.expect_popup():
                page.locator('[data-social-provider="google"]').click()
            page.locator('#account-member').wait_for(state='visible')
            page.wait_for_function("document.getElementById('account-message').textContent.includes('You’re signed in')")
            assert page.locator('#source').input_value()=='Keep my source text.'
            assert page.locator('#paragraph').input_value()=='Keep my working draft.'
            assert page.locator('#api-key').input_value()=='do-not-save-test-key'
            page.locator('#account-close').click()
            page.locator('a[aria-label="Reasoning Studio home"]').click()
            page.emulate_media(reduced_motion='reduce')
            assert page.locator('.mascot-float').evaluate('(node)=>getComputedStyle(node).animationName')=='none'
            page.set_viewport_size({'width':1440,'height':1080})
            page.evaluate('scrollTo({top:0,behavior:"instant"})')
            page.locator('[data-info-page="contact"]').click()
            assert page.locator('#info-dialog').is_visible()
            assert page.locator('#info-body a').get_attribute('href')=='https://github.com/sfstast/essaygrader/issues'
            page.locator('#info-close').click()
            page.locator('[data-info-page="privacy"]').click()
            assert 'Neon' in page.locator('#info-body').inner_text()
            page.keyboard.press('Escape')
            page.screenshot(path='/tmp/reasoning-studio-interactive-home.png',full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path='/tmp/reasoning-studio-interactive-home-mobile.png',full_page=True)
            assert page.evaluate('localStorage.length')==0 and page.evaluate('sessionStorage.length')==0
            assert not errors,errors
            browser.close()
        print('PASS study browser: welcome goals, account signup/logout/profile, vocabulary grading/reuse, free identification, sentence review/reuse, pattern filters, mocked social popup, safe rendering, state preservation, mobile layout')
    finally:
        server.terminate();server.wait(timeout=10)
